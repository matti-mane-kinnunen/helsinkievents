"""Render the static HTML page (Finnish UI)."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import TYPE_CHECKING

from .model import Event

if TYPE_CHECKING:
    from .build import Result

WEEKDAYS = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]
WD_SHORT = ["ma", "ti", "ke", "to", "pe", "la", "su"]
MONTHS = ["tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta", "toukokuuta", "kesäkuuta",
          "heinäkuuta", "elokuuta", "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta"]
STATUS_LABEL = {"cancelled": "Peruttu", "postponed": "Siirretty"}


def fi_date(d: date, long: bool = True) -> str:
    if long:
        return f"{WEEKDAYS[d.weekday()]} {d.day}. {MONTHS[d.month - 1]}"
    return f"{WD_SHORT[d.weekday()]} {d.day}.{d.month}."


def fi_time(dt: datetime) -> str:
    return f"{dt.hour}.{dt.minute:02d}"


def time_label(ev: Event, day: date | None = None) -> str:
    """'klo 18.00–20.00', 'koko päivä', or a date range for multi-day events."""
    if ev.duration_days > 1:
        rng = f"{ev.start_date.day}.{ev.start_date.month}.–{ev.end_date.day}.{ev.end_date.month}."
        if not ev.all_day and day == ev.start_date:
            return f"klo {fi_time(ev.start)} · {rng}"
        return rng
    if ev.all_day:
        return "koko päivä"
    if ev.end and ev.end != ev.start:
        return f"klo {fi_time(ev.start)}–{fi_time(ev.end)}"
    return f"klo {fi_time(ev.start)}"


def e(s: str) -> str:
    return escape(s or "", quote=True)


def card(ev: Event, day: date | None = None, show_date: bool = False) -> str:
    title = e(ev.title)
    if ev.url:
        title = f'<a href="{e(ev.url)}" rel="noopener" target="_blank">{title}</a>'
    status = ""
    if ev.status in STATUS_LABEL:
        status = f'<span class="badge badge-{ev.status}">{STATUS_LABEL[ev.status]}</span> '
    when = time_label(ev, day)
    if show_date and ev.duration_days == 1:
        when = f"{fi_date(ev.start_date, long=False)} {when}"
    place = e(ev.place)
    if ev.address:
        place = f"{place}<span class=\"addr\">, {e(ev.address)}</span>" if place else e(ev.address)
    search = " ".join([ev.title, ev.place, ev.address, ev.summary, " ".join(ev.tags)]).casefold()
    return f"""<article class="event{' is-' + ev.status if ev.status != 'scheduled' else ''}" data-search="{e(search)}">
  <div class="when">{e(when)}</div>
  <div class="body">
    <h3>{status}{title}</h3>
    {f'<p class="place">{place}</p>' if place else ''}
    {f'<p class="summary">{e(ev.summary)}</p>' if ev.summary else ''}
    <p class="meta">{e(ev.source)}</p>
  </div>
</article>"""


def day_block(d: date, events: list[Event]) -> str:
    cards = "\n".join(card(ev, d) for ev in events)
    return f"""<section class="day" data-date="{d.isoformat()}">
  <h2 class="dayhead"><span>{fi_date(d).capitalize()}</span><small>{len(events)} tapahtuma{'a' if len(events) != 1 else ''}</small></h2>
  {cards}
</section>"""


def render_page(res: "Result", cfg: dict) -> str:
    site = cfg.get("site", {})
    title = site.get("title", "Helsingin tapahtumat")
    repo = site.get("repo_url", "")
    today_cards = "\n".join(card(ev, res.today) for ev in res.today_events) or \
        '<p class="empty">Ei tapahtumia tänään valituista lähteistä.</p>'
    upcoming = "\n".join(day_block(d, evs) for d, evs in res.upcoming.items()) or \
        '<p class="empty">Ei tulevia tapahtumia.</p>'
    ongoing = ""
    if res.ongoing:
        ongoing = f"""<details class="ongoing" id="kaynnissa">
  <summary><h2>Pitkäkestoiset ja käynnissä olevat <small>({len(res.ongoing)})</small></h2></summary>
  <p class="hint">Näyttelyt ja muut yli viikon kestävät tapahtumat.</p>
  {''.join(card(ev) for ev in res.ongoing)}
</details>"""
    total = sum(map(len, res.upcoming.values()))
    sources = "".join(
        f"<li>{e(s['name'])}: {s['count']} {'' if s['ok'] else '⚠ haku epäonnistui'}</li>"
        for s in res.source_stats)
    add_link = f'<a href="{e(repo)}/issues/new?template=add-event.yml">Lisää tapahtuma</a>' if repo else ""
    gen = res.generated
    return f"""<!doctype html>
<html lang="fi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="Helsingin tapahtumat tänään ja seuraavan kuukauden aikana.">
<link rel="alternate" type="application/json" href="events.json">
<style>{CSS}</style>
</head>
<body data-built="{res.today.isoformat()}">
<header class="top">
  <div class="wrap">
    <h1>{e(title)}</h1>
    <p class="sub">Päivitetty {fi_date(gen.date())} klo {fi_time(gen)} · {len(res.today_events)} tänään · {total} tulossa {fi_date(res.window_end, long=False)} asti</p>
    <nav><a href="#tanaan">Tänään</a><a href="#tulevat">Tulevat</a>{'<a href="#kaynnissa">Pitkäkestoiset</a>' if res.ongoing else ''}{add_link}</nav>
    <input id="q" type="search" placeholder="Hae tapahtumia (nimi, paikka, aihe)…" aria-label="Hae tapahtumia">
  </div>
</header>
<main class="wrap">
  <p id="stale" class="notice" hidden></p>
  <section id="tanaan" class="today">
    <h2 class="sectionhead">Tänään <small>{fi_date(res.today)}</small></h2>
    <div id="today-list">{today_cards}</div>
  </section>
  <section id="tulevat">
    <h2 class="sectionhead">Seuraavan kuukauden tapahtumat</h2>
    {upcoming}
  </section>
  {ongoing}
  <p id="noresults" class="empty" hidden>Ei hakutuloksia.</p>
</main>
<footer class="wrap">
  <p>Lähteet:</p><ul>{sources}</ul>
  <p>Sivu päivittyy joka yö klo 3. {add_link}{' · <a href="' + e(repo) + '">Lähdekoodi</a>' if repo else ''} · <a href="events.json">events.json</a></p>
</footer>
<script>{JS}</script>
</body>
</html>
"""


CSS = """
:root{--bg:#f7f6f2;--fg:#1d1d1b;--muted:#6b6a64;--card:#fff;--line:#e3e1da;--accent:#0047b6;--today:#fff6d6;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--muted:#a3a29b;--card:#1f1f1d;--line:#34332f;--accent:#8ab4ff;--today:#2a2617;--bad:#ff8a80}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
.top{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2;padding:12px 0}
.top h1{margin:0;font-size:1.5rem}
.sub{margin:2px 0 8px;color:var(--muted);font-size:.9rem}
nav{display:flex;gap:14px;flex-wrap:wrap;font-size:.95rem;margin-bottom:8px}
#q{width:100%;padding:8px 10px;font:inherit;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
.sectionhead{font-size:1.3rem;margin:28px 0 8px}
.sectionhead small,.dayhead small{color:var(--muted);font-weight:400;font-size:.85rem;margin-left:8px}
.today{background:var(--today);margin:16px -16px 0;padding:4px 16px 12px;border-radius:12px}
.dayhead{font-size:1.05rem;margin:22px 0 6px;padding-bottom:4px;border-bottom:2px solid var(--line);position:sticky;top:var(--hh,150px);background:var(--bg);z-index:1}
.event{display:grid;grid-template-columns:118px 1fr;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0}
.event h3{margin:0;font-size:1.02rem;line-height:1.3}
.event h3 a{text-decoration:none}
.event h3 a:hover{text-decoration:underline}
.event p{margin:3px 0 0}
.when{font-weight:600;font-variant-numeric:tabular-nums;font-size:.92rem}
.place{font-size:.92rem}
.addr{color:var(--muted)}
.summary{font-size:.92rem;color:var(--fg);opacity:.9}
.meta{font-size:.75rem;color:var(--muted)}
.badge{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;padding:1px 6px;border-radius:4px;background:var(--bad);color:#fff;vertical-align:2px}
.is-cancelled h3 a,.is-cancelled h3{text-decoration:line-through}
.is-cancelled .badge{text-decoration:none;display:inline-block}
.empty,.hint{color:var(--muted)}
.notice{background:var(--today);padding:8px 12px;border-radius:8px;margin-top:12px}
details.ongoing summary{cursor:pointer;list-style:none}
details.ongoing summary h2{display:inline;font-size:1.2rem}
details.ongoing{margin:28px 0}
footer{color:var(--muted);font-size:.85rem;padding:24px 16px 48px}
footer ul{margin:4px 0 12px;padding-left:18px}
@media (max-width:560px){.event{grid-template-columns:1fr;gap:2px}.top{position:static}.dayhead{top:0}}
"""

# Client-side helpers:
#  * search box filters cards
#  * if the page is opened on a later day than it was built (e.g. the nightly build
#    failed), past days are hidden and the matching day is shown as "today".
JS = r"""
(function(){
  var top=document.querySelector('.top');
  function hh(){document.documentElement.style.setProperty('--hh',(top.offsetHeight)+'px')}
  hh();addEventListener('resize',hh);
  var now=new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Helsinki'}).format(new Date());
  var built=document.body.dataset.built;
  if(now>built){
    document.querySelectorAll('section.day').forEach(function(s){
      if(s.dataset.date<now) s.remove();
      else if(s.dataset.date===now){
        var list=document.getElementById('today-list');list.innerHTML='';
        s.querySelectorAll('.event').forEach(function(a){list.appendChild(a)});s.remove();
        document.querySelector('#tanaan .sectionhead small').textContent=s.querySelector('.dayhead span').textContent;
      }
    });
    var n=document.getElementById('stale');n.hidden=false;
    n.textContent='Huom: sivun tiedot ovat päivältä '+built.split('-').reverse().map(Number).join('.')+'. Uusin päivitys ei ole vielä onnistunut.';
  }
  var q=document.getElementById('q'),cards=[].slice.call(document.querySelectorAll('.event'));
  q.addEventListener('input',function(){
    var t=q.value.trim().toLowerCase(),any=false;
    cards.forEach(function(c){var m=!t||c.dataset.search.indexOf(t)>=0;c.hidden=!m;any=any||m});
    document.querySelectorAll('section.day').forEach(function(s){s.hidden=!s.querySelector('.event:not([hidden])')});
    var o=document.querySelector('details.ongoing');if(o&&t)o.open=true;
    document.getElementById('noresults').hidden=any;
  });
})();
"""
