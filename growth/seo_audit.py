"""Deterministic static-site SEO Auditor for RizzaFit AI Growth (PR 4.2, zero LLM, zero external I/O)."""

import contextlib
import datetime
import json
import os
import re
import sqlite3
import time
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .db import init_growth_db, record_audit_event

SEO_SEVERITIES = ('critical', 'high', 'medium', 'low', 'info')
SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}

KNOWN_PUBLIC_HOST = 'rizzafit.ru'


def _fmt_iso(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return ''


class _SeoHtmlParser(HTMLParser):
    """Lightweight stdlib HTML extractor for deterministic SEO inspection."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.html_lang = ''
        self.title_parts = []
        self._in_title = False
        self.h1_list = []
        self._in_h1 = False
        self._h1_buf = []
        self.description = None
        self.robots_meta = None
        self.viewport = None
        self.canonical = None
        self.og = {}
        self.images_total = 0
        self.images_missing_alt = 0
        self.links = []
        self.has_spa_root = False

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        attr_map = {str(k).lower(): (v if v is not None else '') for k, v in attrs}

        if t == 'html':
            self.html_lang = attr_map.get('lang', '').strip()
        elif t == 'title':
            self._in_title = True
        elif t == 'h1':
            self._in_h1 = True
            self._h1_buf = []
        elif t == 'main' and attr_map.get('id', '').strip() == 'app':
            self.has_spa_root = True
        elif t == 'meta':
            name = attr_map.get('name', '').strip().lower()
            prop = attr_map.get('property', '').strip().lower()
            content = attr_map.get('content', '').strip()
            if name == 'description' and self.description is None:
                self.description = content
            elif name == 'robots' and self.robots_meta is None:
                self.robots_meta = content
            elif name == 'viewport' and self.viewport is None:
                self.viewport = content
            elif prop.startswith('og:'):
                self.og[prop] = content
        elif t == 'link':
            rels = [r.strip().lower() for r in attr_map.get('rel', '').split()]
            if 'canonical' in rels and self.canonical is None:
                self.canonical = attr_map.get('href', '').strip()
        elif t == 'img':
            self.images_total += 1
            # HTML5 allows alt="" for decorative images; flag only missing alt attribute
            if 'alt' not in attr_map:
                self.images_missing_alt += 1
        elif t == 'a':
            if 'href' in attr_map:
                self.links.append(attr_map['href'].strip())

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == 'title':
            self._in_title = False
        elif t == 'h1' and self._in_h1:
            self._in_h1 = False
            txt = ' '.join(''.join(self._h1_buf).split()).strip()
            self.h1_list.append(txt)

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self._h1_buf.append(data)


def _is_within_real(path_real, root_real):
    try:
        return os.path.commonpath([root_real, path_real]) == root_real
    except ValueError:
        return False


def _rel_to_url(rel_path):
    norm = rel_path.replace(os.sep, '/').lstrip('/')
    if norm == 'index.html':
        return '/'
    if norm.endswith('/index.html'):
        return '/' + norm[:-len('index.html')]
    return '/' + norm


def _resolve_local_target(site_real, page_rel, raw_href):
    """Resolve internal href against site_dir safely; return (checkable, exists, resolved_url)."""
    href = str(raw_href or '').strip()
    if not href or href.startswith('#') or href.lower().startswith(('mailto:', 'tel:', 'javascript:', 'data:', 'blob:')):
        return False, True, ''

    parsed = urllib.parse.urlparse(href)
    if parsed.scheme in ('http', 'https'):
        host = (parsed.netloc or '').lower()
        if host not in (KNOWN_PUBLIC_HOST, 'www.' + KNOWN_PUBLIC_HOST):
            return False, True, ''  # external URL -> unknown without network
        url_path = parsed.path or '/'
    elif parsed.scheme:
        return False, True, ''
    else:
        base_dir_url = '/' + os.path.dirname(page_rel.replace(os.sep, '/')).strip('/')
        if not base_dir_url.endswith('/'):
            base_dir_url += '/'
        url_path = parsed.path
        if not url_path:
            return False, True, ''
        if not url_path.startswith('/'):
            url_path = urllib.parse.urljoin(base_dir_url, url_path)

    # Dynamic backend/API endpoints or exercise/workout client prefixes are not static HTML files
    if url_path.startswith('/api/') or url_path.startswith('/server_data/'):
        return False, True, url_path
    if re.match(r'^/(exercise|workout|program)-\d+$', url_path):
        return False, True, url_path

    rel_fs = url_path.lstrip('/')
    if not rel_fs or url_path.endswith('/'):
        cand = os.path.realpath(os.path.join(site_real, rel_fs, 'index.html'))
    else:
        cand = os.path.realpath(os.path.join(site_real, rel_fs))
    if not _is_within_real(cand, site_real):
        return True, False, url_path

    if os.path.isfile(cand):
        return True, True, url_path
    if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, 'index.html')):
        return True, True, url_path
    return True, False, url_path


def _discover_html_files(site_dir):
    site_real = os.path.realpath(site_dir)
    found = []
    for root, dirs, files in os.walk(site_real):
        # Skip heavy asset subdirectories and excluded legacy fitify directory
        dirs[:] = sorted(
            d for d in dirs
            if d not in ('uploads', 'audio', 'anatomy', 'thumbs', 'muscles', 'data', 'img', 'content', 'fitify')
        )
        for fn in sorted(files):
            if not fn.lower().endswith('.html'):
                continue
            full = os.path.realpath(os.path.join(root, fn))
            if not _is_within_real(full, site_real):
                continue
            rel = os.path.relpath(full, site_real)
            found.append((rel, full))
    return site_real, sorted(found, key=lambda x: x[0])


def _parse_robots_txt(site_real):
    path = os.path.realpath(os.path.join(site_real, 'robots.txt'))
    if not _is_within_real(path, site_real) or not os.path.isfile(path):
        return {'exists': False, 'raw': '', 'disallows': [], 'allows': [], 'sitemaps': []}
    with open(path, encoding='utf-8', errors='replace') as f:
        raw = f.read()
    disallows = []
    allows = []
    sitemaps = []
    in_star = False
    for line in raw.splitlines():
        clean = line.split('#', 1)[0].strip()
        if not clean or ':' not in clean:
            continue
        k, v = [p.strip() for p in clean.split(':', 1)]
        kl = k.lower()
        if kl == 'user-agent':
            in_star = (v == '*')
        elif kl == 'disallow' and in_star:
            disallows.append(v)
        elif kl == 'allow' and in_star:
            allows.append(v)
        elif kl == 'sitemap':
            sitemaps.append(v)
    return {'exists': True, 'raw': raw, 'disallows': disallows, 'allows': allows, 'sitemaps': sitemaps}


def _parse_sitemap_xml(site_real):
    path = os.path.realpath(os.path.join(site_real, 'sitemap.xml'))
    if not _is_within_real(path, site_real) or not os.path.isfile(path):
        return {'exists': False, 'valid': False, 'urls': [], 'error': 'Файл sitemap.xml не найден'}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        urls = []
        for elem in root.iter():
            if elem.tag.endswith('loc') and elem.text:
                urls.append(elem.text.strip())
        return {'exists': True, 'valid': True, 'urls': urls, 'error': ''}
    except Exception as e:
        return {'exists': True, 'valid': False, 'urls': [], 'error': str(e)[:200]}


def _add_issue(issues, *, page_url, issue_type, severity, description, recommendation, field_name='', current_value=''):
    issues.append({
        'pageUrl': page_url,
        'issueType': issue_type,
        'severity': severity if severity in SEO_SEVERITIES else 'info',
        'status': 'open',
        'description': description,
        'recommendation': recommendation,
        'fieldName': field_name,
        'currentValue': str(current_value or '')[:500],
    })


def scan_site_seo(site_dir, *, checked_at=None):
    """Run deterministic SEO checks directly against local HTML, robots.txt, and sitemap.xml."""
    ts = int(checked_at if checked_at is not None else time.time())
    checked_iso = _fmt_iso(ts)

    unknown_checks = [
        {
            'check': 'external_links_reachability',
            'status': 'unknown',
            'reason': 'Внешние HTTP-запросы отключены на PR 4.2 ради детерминизма и безопасности.',
        },
        {
            'check': 'search_console_indexing',
            'status': 'unknown',
            'reason': 'Google Search Console / Яндекс.Вебмастер не подключены.',
        },
        {
            'check': 'spa_hash_routes',
            'status': 'unknown',
            'reason': 'Клиентские SPA-экраны (#/programs, #/workouts, #/coach) рендерятся JS в браузере и не имеют отдельных статических HTML-файлов.',
        },
        {
            'check': 'core_web_vitals',
            'status': 'unknown',
            'reason': 'Полевые метрики LCP / CLS / INP не измеряются локальным HTML-сканером.',
        },
    ]

    if not site_dir or not os.path.isdir(site_dir):
        return {
            'ok': True,
            'status': 'unknown',
            'checkedAt': ts,
            'checkedAtIso': checked_iso,
            'pagesChecked': 0,
            'pages': [],
            'issues': [],
            'summary': {'total': 0, **{s: 0 for s in SEO_SEVERITIES}},
            'robotsCheck': {'exists': False},
            'sitemapCheck': {'exists': False},
            'unknownChecks': unknown_checks,
            'error': 'Каталог site/ не найден',
        }

    site_real, html_files = _discover_html_files(site_dir)
    robots = _parse_robots_txt(site_real)
    sitemap = _parse_sitemap_xml(site_real)

    sitemap_paths = set()
    for u in sitemap.get('urls', []):
        p = urllib.parse.urlparse(u).path or '/'
        sitemap_paths.add(p)

    issues = []
    pages = []
    title_index = {}
    desc_index = {}

    for rel, full_path in html_files:
        page_url = _rel_to_url(rel)
        is_admin = (rel.replace(os.sep, '/') == 'admin.html')
        with open(full_path, encoding='utf-8', errors='replace') as f:
            raw_html = f.read()

        parser = _SeoHtmlParser()
        try:
            parser.feed(raw_html)
            parser.close()
        except Exception as e:
            _add_issue(
                issues,
                page_url=page_url,
                issue_type='html_parse_error',
                severity='high',
                description=f'Не удалось разобрать HTML: {str(e)[:120]}',
                recommendation='Проверьте синтаксическую корректность HTML-документа.',
            )
            continue

        title_val = ' '.join(''.join(parser.title_parts).split()).strip()
        desc_val = parser.description
        robots_val = (parser.robots_meta or '').lower()
        noindex = 'noindex' in robots_val
        nofollow = 'nofollow' in robots_val
        blocked_by_robots = any(d and (d == '/' or page_url.startswith(d)) for d in robots.get('disallows', []))
        indexable = (not is_admin) and (not noindex) and (not blocked_by_robots)

        pages.append({
            'pageUrl': page_url,
            'file': rel.replace(os.sep, '/'),
            'role': 'admin' if is_admin else 'public',
            'title': title_val,
            'titleLength': len(title_val),
            'descriptionLength': len(desc_val) if desc_val is not None else None,
            'h1Count': len(parser.h1_list),
            'canonical': parser.canonical or '',
            'robotsMeta': parser.robots_meta or '',
            'inSitemap': page_url in sitemap_paths,
            'indexable': indexable,
            'imagesTotal': parser.images_total,
            'imagesMissingAlt': parser.images_missing_alt,
        })

        # 1. Title check
        if not title_val:
            _add_issue(
                issues,
                page_url=page_url,
                issue_type='missing_title',
                severity='critical',
                description='Отсутствует тег <title>.',
                recommendation='Добавьте уникальный <title> длиной 30–60 символов.',
                field_name='title',
                current_value='',
            )
        elif not is_admin:
            title_index.setdefault(title_val.lower(), []).append((page_url, title_val))
            if len(title_val) < 15:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='short_title',
                    severity='medium',
                    description=f'Слишком короткий <title> ({len(title_val)} симв.).',
                    recommendation='Расширьте <title> до 30–60 символов с ключевой темой страницы.',
                    field_name='title',
                    current_value=title_val,
                )
            elif len(title_val) > 65:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='long_title',
                    severity='low',
                    description=f'<title> длиннее рекомендуемых 65 символов ({len(title_val)} симв.) и может обрезаться в выдаче.',
                    recommendation='Сократите <title> до 50–65 символов без потери смысла.',
                    field_name='title',
                    current_value=title_val,
                )

        # 2. Robots meta / indexability
        if is_admin:
            if not noindex:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='admin_missing_noindex',
                    severity='high',
                    description='Служебная страница админки не содержит <meta name="robots" content="noindex,nofollow">.',
                    recommendation='Добавьте noindex,nofollow на admin.html.',
                    field_name='robots_meta',
                    current_value=parser.robots_meta or '',
                )
        else:
            if parser.robots_meta is None:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='missing_robots_meta',
                    severity='info',
                    description='Не задан явный <meta name="robots"> (по умолчанию разрешена индексация).',
                    recommendation='При желании явно укажите <meta name="robots" content="index, follow">.',
                    field_name='robots_meta',
                    current_value='',
                )
            elif noindex:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='public_page_noindex',
                    severity='critical',
                    description=f'Публичная страница закрыта от индексации ({parser.robots_meta}).',
                    recommendation='Удалите noindex, если страница должна участвовать в поиске.',
                    field_name='robots_meta',
                    current_value=parser.robots_meta,
                )

            # 3. Meta description
            if desc_val is None or not desc_val:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='missing_meta_description',
                    severity='high',
                    description='Отсутствует <meta name="description">.',
                    recommendation='Добавьте уникальное описание длиной 120–160 символов.',
                    field_name='meta_description',
                    current_value='',
                )
            else:
                desc_index.setdefault(desc_val.lower(), []).append((page_url, desc_val))
                if len(desc_val) < 50:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='short_meta_description',
                        severity='medium',
                        description=f'Короткий meta description ({len(desc_val)} симв.).',
                        recommendation='Увеличьте meta description до 120–160 символов.',
                        field_name='meta_description',
                        current_value=desc_val,
                    )
                elif len(desc_val) > 165:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='long_meta_description',
                        severity='low',
                        description=f'Meta description длиннее 165 символов ({len(desc_val)} симв.).',
                        recommendation='Сократите описание до 120–160 символов.',
                        field_name='meta_description',
                        current_value=desc_val,
                    )

            # 4. H1
            if len(parser.h1_list) == 0:
                if parser.has_spa_root:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='spa_missing_static_h1',
                        severity='medium',
                        description='На корневой SPA-странице отсутствует статический <h1> до выполнения JavaScript.',
                        recommendation='Добавьте статический семантический <h1> (или SSR/fallback заголовок) в HTML для краулеров без JS.',
                        field_name='h1',
                        current_value='',
                    )
                else:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='missing_h1',
                        severity='high',
                        description='На публичной странице отсутствует заголовок <h1>.',
                        recommendation='Добавьте ровно один релевантный заголовок <h1> на страницу.',
                        field_name='h1',
                        current_value='',
                    )
            elif len(parser.h1_list) > 1:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='multiple_h1',
                    severity='low',
                    description=f'На странице найдено несколько тегов <h1> ({len(parser.h1_list)}).',
                    recommendation='Оставьте один основной <h1>, остальные заголовки понизьте до <h2>.',
                    field_name='h1',
                    current_value=' | '.join(parser.h1_list[:3]),
                )

            # 5. Canonical
            if not parser.canonical:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='missing_canonical',
                    severity='high',
                    description='Отсутствует <link rel="canonical">.',
                    recommendation=f'Укажите <link rel="canonical" href="https://{KNOWN_PUBLIC_HOST}{page_url}">.',
                    field_name='canonical',
                    current_value='',
                )
            else:
                cp = urllib.parse.urlparse(parser.canonical)
                if cp.scheme != 'https' or not cp.netloc:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='invalid_canonical',
                        severity='medium',
                        description=f'Некорректный canonical URL ({parser.canonical}).',
                        recommendation='Используйте абсолютный HTTPS URL в canonical.',
                        field_name='canonical',
                        current_value=parser.canonical,
                    )
                elif (cp.path or '/') != page_url:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='canonical_path_mismatch',
                        severity='medium',
                        description=f'Canonical ({cp.path or "/"}) не совпадает с URL страницы ({page_url}).',
                        recommendation='Проверьте, что canonical ведёт на канонический URL самой страницы.',
                        field_name='canonical',
                        current_value=parser.canonical,
                    )

            # 6. Images without alt
            if parser.images_missing_alt > 0:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='images_missing_alt',
                    severity='medium',
                    description=f'Найдены теги <img> без атрибута alt: {parser.images_missing_alt} из {parser.images_total}.',
                    recommendation='Добавьте осмысленный alt для контентных изображений или alt="" для декоративных иконок.',
                    field_name='alt',
                    current_value=str(parser.images_missing_alt),
                )

            # 7. Technical SEO tags
            if not parser.html_lang:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='missing_html_lang',
                    severity='medium',
                    description='У корневого тега <html> не задан атрибут lang.',
                    recommendation='Добавьте <html lang="ru">.',
                    field_name='other',
                    current_value='',
                )
            if not parser.viewport:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='missing_viewport',
                    severity='high',
                    description='Отсутствует <meta name="viewport">.',
                    recommendation='Добавьте стандартный тег viewport для корректной мобильной индексации.',
                    field_name='other',
                    current_value='',
                )
            elif 'user-scalable=no' in parser.viewport.lower() or 'maximum-scale=1' in parser.viewport.lower():
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='viewport_zoom_disabled',
                    severity='low',
                    description=f'Viewport ограничивает масштабирование пользователем ({parser.viewport}).',
                    recommendation='Уберите user-scalable=no / maximum-scale=1.0 ради доступности (Lighthouse Accessibility/SEO).',
                    field_name='other',
                    current_value=parser.viewport,
                )
            if not parser.og.get('og:title') or not parser.og.get('og:description'):
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='missing_open_graph',
                    severity='low',
                    description='Отсутствуют базовые Open Graph метатеги (og:title / og:description).',
                    recommendation='Добавьте og:title, og:description и og:image для корректного превью в соцсетях и мессенджерах.',
                    field_name='og_title',
                    current_value=parser.og.get('og:title', ''),
                )
            elif parser.og.get('og:image'):
                checkable, exists, _ = _resolve_local_target(site_real, rel, parser.og['og:image'])
                if checkable and not exists:
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='broken_og_image',
                        severity='medium',
                        description=f'Локальный файл og:image не найден ({parser.og["og:image"]}).',
                        recommendation='Укажите существующее изображение в site/img или site/content/uploads.',
                        field_name='other',
                        current_value=parser.og['og:image'],
                    )

            # 8. Broken local internal links
            seen_broken = set()
            for href in parser.links:
                checkable, exists, resolved_u = _resolve_local_target(site_real, rel, href)
                if checkable and not exists and resolved_u not in seen_broken:
                    seen_broken.add(resolved_u)
                    _add_issue(
                        issues,
                        page_url=page_url,
                        issue_type='broken_internal_link',
                        severity='high',
                        description=f'Битая локальная внутренняя ссылка: {href} (ресурс не найден).',
                        recommendation='Исправьте href или восстановите целевую страницу.',
                        field_name='other',
                        current_value=href,
                    )

            # 9. Sitemap coverage
            if sitemap['exists'] and sitemap['valid'] and not noindex and page_url not in sitemap_paths:
                _add_issue(
                    issues,
                    page_url=page_url,
                    issue_type='page_missing_from_sitemap',
                    severity='medium',
                    description='Индексируемая страница отсутствует в sitemap.xml.',
                    recommendation=f'Добавьте https://{KNOWN_PUBLIC_HOST}{page_url} в sitemap.xml.',
                    field_name='sitemap_xml',
                    current_value=page_url,
                )

    # Duplicate titles & descriptions across public pages
    for _tk, occs in title_index.items():
        if len(occs) > 1:
            urls = ', '.join(u for u, _ in occs)
            _add_issue(
                issues,
                page_url=urls,
                issue_type='duplicate_title',
                severity='high',
                description=f'Обнаружен дублирующийся <title> на нескольких страницах: {urls}.',
                recommendation='Сделайте <title> уникальным для каждой страницы.',
                field_name='title',
                current_value=occs[0][1],
            )
    for _dk, occs in desc_index.items():
        if len(occs) > 1:
            urls = ', '.join(u for u, _ in occs)
            _add_issue(
                issues,
                page_url=urls,
                issue_type='duplicate_meta_description',
                severity='high',
                description=f'Обнаружен дублирующийся meta description на страницах: {urls}.',
                recommendation='Напишите уникальные meta description для каждой страницы.',
                field_name='meta_description',
                current_value=occs[0][1],
            )

    # Global robots.txt checks
    if not robots['exists']:
        _add_issue(
            issues,
            page_url='/robots.txt',
            issue_type='missing_robots_txt',
            severity='high',
            description='Отсутствует файл robots.txt.',
            recommendation='Создайте robots.txt с директивами Allow/Disallow и ссылкой на Sitemap.',
            field_name='robots_txt',
            current_value='',
        )
    else:
        if '/' in robots['disallows']:
            _add_issue(
                issues,
                page_url='/robots.txt',
                issue_type='robots_disallow_all',
                severity='critical',
                description='В robots.txt задано Disallow: / — сайт полностью закрыт от индексации.',
                recommendation='Уберите Disallow: / и оставьте запрет только для /admin.html, /api/ и /server_data/.',
                field_name='robots_txt',
                current_value='Disallow: /',
            )
        if not robots['sitemaps']:
            _add_issue(
                issues,
                page_url='/robots.txt',
                issue_type='robots_missing_sitemap',
                severity='medium',
                description='В robots.txt не указана директива Sitemap.',
                recommendation=f'Добавьте строку Sitemap: https://{KNOWN_PUBLIC_HOST}/sitemap.xml.',
                field_name='robots_txt',
                current_value='',
            )
        for req_dis in ('/admin.html', '/api/'):
            if req_dis not in robots['disallows']:
                _add_issue(
                    issues,
                    page_url='/robots.txt',
                    issue_type='robots_missing_private_disallow',
                    severity='high',
                    description=f'В robots.txt отсутствует Disallow: {req_dis}.',
                    recommendation=f'Добавьте Disallow: {req_dis} в секцию User-agent: *.',
                    field_name='robots_txt',
                    current_value='',
                )
        if '/' not in robots['disallows'] and '/fitify/' not in robots['disallows']:
            _add_issue(
                issues,
                page_url='/robots.txt',
                issue_type='robots_missing_fitify_disallow',
                severity='medium',
                description='В robots.txt отсутствует Disallow: /fitify/ для исключения стороннего каталога из индексации RizzaFit.',
                recommendation='Добавьте Disallow: /fitify/ в секцию User-agent: *.',
                field_name='robots_txt',
                current_value='',
            )

    # Global sitemap.xml checks
    if not sitemap['exists']:
        _add_issue(
            issues,
            page_url='/sitemap.xml',
            issue_type='missing_sitemap_xml',
            severity='high',
            description='Отсутствует файл sitemap.xml.',
            recommendation='Создайте валидный sitemap.xml со всеми публичными страницами.',
            field_name='sitemap_xml',
            current_value='',
        )
    elif not sitemap['valid']:
        _add_issue(
            issues,
            page_url='/sitemap.xml',
            issue_type='invalid_sitemap_xml',
            severity='critical',
            description=f'Ошибка разбора XML в sitemap.xml: {sitemap["error"]}.',
            recommendation='Исправьте XML-разметку sitemap.xml.',
            field_name='sitemap_xml',
            current_value=sitemap['error'],
        )
    else:
        for sm_url in sitemap['urls']:
            checkable, exists, sm_path = _resolve_local_target(site_real, 'index.html', sm_url)
            sm_clean_path = (sm_path or urllib.parse.urlparse(sm_url).path or '').lower()
            if sm_clean_path == '/fitify' or sm_clean_path.startswith('/fitify/'):
                _add_issue(
                    issues,
                    page_url=sm_path or sm_url,
                    issue_type='sitemap_excluded_fitify_url',
                    severity='high',
                    description=f'URL Fitify ({sm_url}) не должен включаться в sitemap.xml RizzaFit.',
                    recommendation='Удалите все URL /fitify/ из sitemap.xml — развивается только RizzaFit.',
                    field_name='sitemap_xml',
                    current_value=sm_url,
                )
            if checkable and not exists:
                _add_issue(
                    issues,
                    page_url=sm_path or sm_url,
                    issue_type='sitemap_broken_url',
                    severity='high',
                    description=f'URL из sitemap.xml не найден на диске: {sm_url}.',
                    recommendation='Удалите несуществующий URL из sitemap.xml или создайте соответствующую страницу.',
                    field_name='sitemap_xml',
                    current_value=sm_url,
                )
            if any(d and (d == '/' or (sm_path or '/').startswith(d)) for d in robots['disallows']):
                _add_issue(
                    issues,
                    page_url=sm_path or sm_url,
                    issue_type='sitemap_robots_conflict',
                    severity='high',
                    description=f'URL {sm_url} присутствует в sitemap.xml, но запрещён в robots.txt.',
                    recommendation='Разрешите индексацию URL в robots.txt или уберите его из sitemap.xml.',
                    field_name='sitemap_xml',
                    current_value=sm_url,
                )

    issues.sort(key=lambda it: (SEVERITY_ORDER.get(it['severity'], 9), it['pageUrl'], it['issueType']))
    sev_counts = {s: 0 for s in SEO_SEVERITIES}
    for it in issues:
        sev_counts[it['severity']] += 1

    return {
        'ok': True,
        'status': 'ok',
        'checkedAt': ts,
        'checkedAtIso': checked_iso,
        'pagesChecked': len(pages),
        'pages': pages,
        'issues': issues,
        'summary': {'total': len(issues), **sev_counts},
        'robotsCheck': {'exists': robots['exists'], 'disallows': robots['disallows'], 'sitemaps': robots['sitemaps']},
        'sitemapCheck': {'exists': sitemap['exists'], 'valid': sitemap['valid'], 'urlCount': len(sitemap['urls'])},
        'unknownChecks': unknown_checks,
        'source': 'site/*.html + robots.txt + sitemap.xml (deterministic)',
    }


def run_seo_audit(db_file, db_lock, *, site_dir, actor='admin', actor_ip=''):
    """Execute deterministic SEO audit, persist run & issues to SQLite, and append to audit log."""
    report = scan_site_seo(site_dir)
    ts = int(report['checkedAt'])

    meta_blob = {
        'pages': report['pages'],
        'robotsCheck': report['robotsCheck'],
        'sitemapCheck': report['sitemapCheck'],
        'unknownChecks': report['unknownChecks'],
    }
    with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
        conn.row_factory = sqlite3.Row
        init_growth_db(conn)
        cur = conn.execute(
            'INSERT INTO growth_seo_audit_runs (created_at, pages_checked, issues_total, summary_json, checks_json) '
            'VALUES (?, ?, ?, ?, ?)',
            (
                ts,
                int(report['pagesChecked']),
                int(report['summary']['total']),
                json.dumps(report['summary'], ensure_ascii=False),
                json.dumps(meta_blob, ensure_ascii=False),
            ),
        )
        run_id = int(cur.lastrowid)
        for idx, it in enumerate(report['issues']):
            ic = conn.execute(
                'INSERT INTO growth_seo_issues '
                '(run_id, page_url, issue_type, severity, status, description, recommendation, field_name, current_value, checked_at) '
                'VALUES (?, ?, ?, ?, "open", ?, ?, ?, ?, ?)',
                (
                    run_id,
                    it['pageUrl'],
                    it['issueType'],
                    it['severity'],
                    it['description'],
                    it['recommendation'],
                    it['fieldName'],
                    it['currentValue'],
                    ts,
                ),
            )
            it['id'] = int(ic.lastrowid)
            it['runId'] = run_id
            it['checkedAt'] = ts
            it['checkedAtIso'] = report['checkedAtIso']
        conn.commit()

    record_audit_event(
        db_file,
        db_lock,
        action='seo_audit.run',
        module='seo',
        target=f'seo_run:{run_id}',
        status='ok',
        actor=actor,
        actor_ip=actor_ip,
        details={'pagesChecked': report['pagesChecked'], 'issuesTotal': report['summary']['total'], 'critical': report['summary']['critical']},
    )
    report['runId'] = run_id
    return report


def get_latest_seo_audit(db_file, db_lock, *, run_id=None, severity=''):
    """Read persisted SEO audit run and issues (read-only, safe on unmigrated DB)."""
    now = int(time.time())
    sev_f = str(severity or '').strip().lower()
    if sev_f and sev_f != 'all' and sev_f not in SEO_SEVERITIES:
        raise ValueError('Некорректный фильтр severity')

    if not db_file or not os.path.isfile(db_file):
        return {'ok': True, 'status': 'unavailable', 'dbHealth': 'missing', 'hasRun': False, 'issues': [], 'pages': []}

    try:
        with db_lock, contextlib.closing(sqlite3.connect(db_file)) as conn:
            conn.row_factory = sqlite3.Row
            tbl = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='growth_seo_audit_runs'"
            ).fetchone()
            if not tbl:
                return {'ok': True, 'status': 'unavailable', 'dbHealth': 'missing_table', 'hasRun': False, 'issues': [], 'pages': []}

            if run_id is not None:
                run_row = conn.execute('SELECT * FROM growth_seo_audit_runs WHERE id = ?', (int(run_id),)).fetchone()
            else:
                run_row = conn.execute('SELECT * FROM growth_seo_audit_runs ORDER BY id DESC LIMIT 1').fetchone()
            if not run_row:
                return {
                    'ok': True,
                    'status': 'ok',
                    'dbHealth': 'ok',
                    'hasRun': False,
                    'runId': None,
                    'checkedAt': None,
                    'checkedAtIso': '',
                    'pagesChecked': 0,
                    'pages': [],
                    'issues': [],
                    'summary': {'total': 0, **{s: 0 for s in SEO_SEVERITIES}},
                    'unknownChecks': scan_site_seo(None)['unknownChecks'],
                    'source': 'flexa.db:growth_seo_audit_runs',
                    'updatedAt': _fmt_iso(now),
                }

            rid = int(run_row['id'])
            summary = json.loads(run_row['summary_json'] or '{}')
            checks = json.loads(run_row['checks_json'] or '{}')

            where_sql = 'WHERE run_id = ?'
            params = [rid]
            if sev_f and sev_f != 'all':
                where_sql += ' AND severity = ?'
                params.append(sev_f)
            issue_rows = conn.execute(
                f'SELECT * FROM growth_seo_issues {where_sql} ORDER BY id ASC',
                tuple(params),
            ).fetchall()
    except sqlite3.Error:
        return {'ok': True, 'status': 'unavailable', 'dbHealth': 'corrupted', 'hasRun': False, 'issues': [], 'pages': []}

    issues = [
        {
            'id': int(ir['id']),
            'runId': int(ir['run_id']),
            'pageUrl': str(ir['page_url']),
            'issueType': str(ir['issue_type']),
            'severity': str(ir['severity']),
            'status': str(ir['status']),
            'description': str(ir['description']),
            'recommendation': str(ir['recommendation']),
            'fieldName': str(ir['field_name'] or ''),
            'currentValue': str(ir['current_value'] or ''),
            'checkedAt': int(ir['checked_at'] or 0),
            'checkedAtIso': _fmt_iso(ir['checked_at']),
        }
        for ir in issue_rows
    ]
    c_at = int(run_row['created_at'] or 0)
    return {
        'ok': True,
        'status': 'ok',
        'dbHealth': 'ok',
        'hasRun': True,
        'runId': rid,
        'checkedAt': c_at,
        'checkedAtIso': _fmt_iso(c_at),
        'pagesChecked': int(run_row['pages_checked'] or 0),
        'pages': checks.get('pages', []),
        'issues': issues,
        'summary': summary,
        'robotsCheck': checks.get('robotsCheck', {}),
        'sitemapCheck': checks.get('sitemapCheck', {}),
        'unknownChecks': checks.get('unknownChecks', []),
        'source': 'flexa.db:growth_seo_audit_runs',
        'updatedAt': _fmt_iso(c_at),
    }
