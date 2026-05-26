/*
 * Lightweight i18n helper used by login.html, admin.html, join.html and
 * index.html. Translations live in `MESSAGES` keyed by message id. Elements
 * with `data-i18n` (text), `data-i18n-html` (innerHTML) or `data-i18n-attr`
 * (attribute=key,...) are translated on `apply()`.
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'damagerace.lang';
  const COOKIE_NAME = 'damagerace_lang';
  const SUPPORTED = ['de', 'en'];
  const DEFAULT_LANG = 'de';

  const MESSAGES = {
    de: {
      'common.copy':              'Kopieren',
      'common.copied':            'Kopiert.',
      'common.cancel':            'Abbrechen',
      'common.create':            'Erstellen',
      'common.regenerate':        'Neu generieren',
      'common.back':              'Zurueck',
      'common.confirm_reset':     'Wirklich alle Damage-Werte zuruecksetzen?',
      'common.confirm_regen':     'Alten Invite-Link ungueltig machen und neuen erstellen?',
      'common.error':             'Fehler',
      'common.live':              'Live',
      'common.required':          'Pflicht',
      'common.remove':            'Entfernen',
      'common.empty_dash':        '—',

      'lang.toggle_label':        'Sprache',

      'login.subtitle':           'Veranstalter-Login',
      'login.with_twitch':        'Mit Twitch anmelden',
      'login.info_title':         'Keine Anmeldung als Streamer noetig.',
      'login.info_body':          'Wenn du nur an einem Event teilnehmen willst, lade die DamageRace-App, gib den Invite-Code deines Veranstalters ein und installiere den WoT-Mod.',
      'login.footer':             'Mohjos DamageRace · Twitch-Login',

      'admin.logout':             'Abmelden',
      'admin.no_event_top':       'Kein aktives Event',
      'admin.stat.remaining':     'Restdamage',
      'admin.stat.dealt':         'Schaden gesamt',
      'admin.stat.goal':          'Ziel',
      'admin.empty.title':        'Noch kein Event erstellt',
      'admin.empty.hint':         'Klick "Neues Event erstellen" rechts, um zu starten.',
      'admin.no_teams.title':     'Noch keine Teams konfiguriert',
      'admin.no_teams.hint':      'Erstelle ein Event, um Teams + Invite-Links zu generieren.',
      'admin.live_log':           'Live-Log',
      'admin.log.empty':          'Noch keine Damage-Eintraege',
      'admin.controls':           'Event-Steuerung',
      'admin.new_event_btn':      '＋ Neues Event erstellen',
      'admin.adjust_goal':        'Schaden-Ziel anpassen',
      'admin.set':                'Setzen',
      'admin.pause':              '⏸ Pause',
      'admin.resume':             '▶ Fortsetzen',
      'admin.reset':              '↻ Reset',
      'admin.event_invite':       'Event-Einladung',
      'admin.event_invite_hint':  'Allgemeiner Link — Streamer wird ohne Team-Zuordnung registriert.',
      'admin.obs_browser':        'OBS Browser-Source',
      'admin.obs_browser_hint':   'Diese URL als Browser-Source in OBS hinzufuegen (300x180px, transparent).',
      'admin.howto':              'Anleitung',
      'admin.howto.1':            'Team-Invite-Link kopieren und an Streamer schicken.',
      'admin.howto.2':            'Streamer oeffnet <code>DamageRace.exe</code>, waehlt "An Event teilnehmen", traegt Code + WoT-Name ein.',
      'admin.howto.3':            'Die App installiert den WoT-Mod automatisch.',
      'admin.howto.4':            'OBS Browser-Source mit obiger URL einrichten.',
      'admin.team.damage':        'Schaden',
      'admin.team.remaining':     'Rest',
      'admin.team.members':       'Mitglieder',
      'admin.team.no_members':    'Keine Mitglieder — Streamer hinzufuegen oder per Drag & Drop verschieben',
      'admin.team.add_streamer_ph': 'WoT-Name + Enter',
      'admin.team.remove_streamer': 'Streamer entfernen',
      'admin.team.join_self':      'Mich eintragen',
      'admin.team.join_self_title': 'Veranstalter selbst diesem Team zuweisen',
      'admin.team.join_self_prompt': 'Wie heisst dein WoT-Account? (wird einmalig gespeichert)',
      'admin.team.chip_title':     'Streamer-Token anzeigen',
      'admin.team.unassigned':     'Ohne Team (per Drag & Drop einem Team zuweisen)',
      'admin.team.add_team':       'Team hinzufuegen',
      'admin.team.add_team_prompt':'Name des neuen Teams:',
      'admin.team.remove_team':    'Team entfernen',
      'admin.team.remove_confirm': 'Team "{name}" wirklich entfernen? Mitglieder behalten ihre Tokens und werden auf "kein Team" gesetzt — du kannst sie danach per Drag&Drop einem anderen Team zuweisen.',
      'admin.team.rename_title':   'Team umbenennen',
      'admin.team.rename_prompt':  'Neuer Team-Name:',
      'admin.adjust_mode':         'Modus',
      'admin.toast.mode_updated':  'Modus geaendert.',
      'admin.toast.team_added':    'Team hinzugefuegt.',
      'admin.toast.team_removed':  'Team entfernt.',
      'admin.toast.team_renamed':  'Team umbenannt.',
      'admin.counting':            'Wertung',
      'admin.counting_hint':       'Welche Schadensarten zaehlen aufs Ziel?',
      'admin.counting.direct':     'Direkter Schaden',
      'admin.counting.assist':     'Assist (Spot/Track)',
      'admin.toast.counting_updated': 'Wertung aktualisiert.',
      'admin.deadline':            'Deadline',
      'admin.deadline_hint':       'Zeitfenster bis zum Ziel. Bei Ablauf wird das Event pausiert.',
      'admin.deadline_clear':      '✕ Deadline loeschen',
      'admin.deadline_none':       'Keine Deadline gesetzt.',
      'admin.deadline_expired':    '⏱ Deadline abgelaufen.',
      'admin.deadline_in':         'Verbleibend: {time}',
      'admin.toast.deadline_updated': 'Deadline gesetzt.',
      'admin.toast.deadline_cleared': 'Deadline entfernt.',
      'admin.toast.deadline_invalid': 'Deadline ungueltig.',
      'admin.log.type_direct':     'Direkt',
      'admin.log.type_assist':     'Assist',
      'admin.toast.joined_self':   'Du bist dem Team beigetreten.',
      'admin.token.title':         'Streamer-Token',
      'admin.token.hint':          'Dieser Token gehoert in die <code>config.json</code> des WoT-Mods. Pfad: <code>res_mods/&lt;version&gt;/mods/damagerace/config.json</code>.',
      'admin.token.label_name':    'WoT-Name',
      'admin.token.label_token':   'Streamer-Token',
      'admin.token.label_config':  'Fertige config.json',
      'admin.token.copy_config':   'Komplette config.json kopieren',
      'admin.token.install_btn':   '＞  Mod jetzt installieren',
      'admin.token.install_prompt_path': 'WoT konnte nicht automatisch gefunden werden. Bitte vollstaendigen Pfad eingeben (z.B. D:\\World_of_Tanks_EU):',
      'admin.token.missing':       'Kein Token fuer diesen Streamer gefunden.',
      'admin.toast.mod_installed': 'Mod installiert (WoT {ver}). Spiel starten — fertig.',
      'admin.toast.mod_no_wot':    'WoT-Installation nicht gefunden.',
      'admin.toast.mod_install_failed': 'Mod-Installation fehlgeschlagen',
      'admin.confirm.remove_streamer': 'Streamer wirklich aus dem Event entfernen?',
      'admin.toast.created':      'Event erstellt.',
      'admin.toast.goal_updated': 'Ziel aktualisiert.',
      'admin.toast.reset_done':   'Event zurueckgesetzt.',
      'admin.toast.new_link':     'Neuer Einladungslink generiert.',
      'admin.toast.streamer_added': 'Streamer hinzugefuegt.',
      'admin.toast.streamer_moved': 'Streamer verschoben.',
      'admin.toast.streamer_removed': 'Streamer entfernt.',
      'admin.obs_add_btn':         '＋ In OBS hinzufuegen',
      'admin.obs_password_prompt': 'OBS WebSocket-Passwort (siehe OBS → Werkzeuge → WebSocket Server):',
      'admin.toast.obs_added':     'Browser-Source in OBS hinzugefuegt.',
      'admin.toast.obs_existed':   'Browser-Source existiert bereits in OBS.',
      'admin.toast.obs_unreachable': 'OBS nicht erreichbar. WebSocket Server in OBS aktiv?',
      'admin.toast.obs_no_url':    'Overlay-URL noch nicht verfuegbar.',
      'admin.toast.obs_failed':    'OBS-Aktion fehlgeschlagen',
      'common.save':               'Speichern',
      'admin.integrations':        'Integrationen',
      'admin.integrations_hint':   'Discord-Webhook fuer Event-Recap. Beim Beenden wird ein Embed mit Gewinner-Team, Top-Streamern und Standings gepostet.',
      'admin.integrations.test':   'Test-Post',
      'admin.integrations.finish': '🏁 Event beenden & posten',
      'admin.confirm.finish_event': 'Event jetzt beenden und Recap nach Discord posten?',
      'admin.recap_posted_at':     'Recap bereits gepostet am {ts}',
      'admin.toast.discord_saved': 'Discord-Webhook gespeichert.',
      'admin.toast.discord_cleared': 'Discord-Webhook entfernt.',
      'admin.toast.discord_test_sent': 'Test-Post gesendet — siehe Discord-Kanal.',
      'admin.toast.event_finished': 'Event beendet, Recap gepostet.',
      'admin.toast.recap_already_posted': 'Recap wurde bereits gepostet.',
      'admin.wizard.title':       'Neues Event erstellen',
      'admin.wizard.name':        'Event-Name',
      'admin.wizard.name_hint':   'z.B. Mohjos Sommer-Cup',
      'admin.wizard.goal':        'Schaden-Ziel',
      'admin.wizard.mode':        'Modus',
      'admin.wizard.mode_coop':   'Kooperativ',
      'admin.wizard.mode_coop_d': 'Alle Teams an einem gemeinsamen Ziel',
      'admin.wizard.mode_versus': 'Versus',
      'admin.wizard.mode_v_desc': 'Team-Wettstreit: erstes Team am Ziel gewinnt',
      'admin.wizard.teams':       'Teams (2-4)',
      'admin.wizard.add_team':    '＋ Team hinzufuegen',
      'admin.wizard.submit':      'Event erstellen',

      'join.wrong':               'Einladungslink ungueltig',
      'join.wrong_hint':          'Bitte vom Veranstalter einen neuen Link anfordern.',
      'join.invited_to':          'Du wirst eingeladen zu',
      'join.assign_admin':        'Allgemeiner Beitritt — Team wird vom Admin zugewiesen',
      'join.wot_name':            'Dein WoT-Account-Name',
      'join.wot_placeholder':     'z.B. Mohjo_beist',
      'join.submit':              'Beitreten',
      'join.submitting':          'Beitreten…',
      'join.after_info':          'Nach dem Beitritt installierst du die <strong>DamageRace-App</strong> (vom Veranstalter) mit demselben Namen. Dein Schaden wird automatisch fuer das Event gezaehlt.',
      'join.success_prefix':      '✓ Beitritt erfolgreich',
      'join.team_suffix':         ' (Team {team})',
      'join.next_step':           '<strong>Naechster Schritt:</strong> Lade die <strong>DamageRace.exe</strong> ({link}), oeffne sie, klick "An Event teilnehmen" und gib diesen Code ein:',
      'join.releases_link':       'GitHub Releases',
      'join.error_failed':        'Beitritt fehlgeschlagen',
      'join.error_connection':    'Verbindungsfehler.',
      'join.checking_link':       'Pruefe Einladungslink…',
      'join.done':                'Erledigt',

      'overlay.remaining':        'Restschaden',
      'overlay.remaining_to_win': 'Bis zum Sieg',
      'overlay.goal_reached':     '✓ Ziel erreicht!',
      'overlay.paused':           '⏸ Pause',
      'overlay.expired':          '⏱ Zeit abgelaufen',
    },
    en: {
      'common.copy':              'Copy',
      'common.copied':            'Copied.',
      'common.cancel':            'Cancel',
      'common.create':            'Create',
      'common.regenerate':        'Regenerate',
      'common.back':              'Back',
      'common.confirm_reset':     'Really reset all damage values?',
      'common.confirm_regen':     'Invalidate the old invite link and create a new one?',
      'common.error':             'Error',
      'common.live':              'Live',
      'common.required':          'Required',
      'common.remove':            'Remove',
      'common.empty_dash':        '—',

      'lang.toggle_label':        'Language',

      'login.subtitle':           'Organizer login',
      'login.with_twitch':        'Sign in with Twitch',
      'login.info_title':         'No streamer account needed.',
      'login.info_body':          'If you only want to participate, download the DamageRace app, enter the invite code your organizer gave you, and install the WoT mod.',
      'login.footer':             'Mohjos DamageRace · Twitch login',

      'admin.logout':             'Sign out',
      'admin.no_event_top':       'No active event',
      'admin.stat.remaining':     'Remaining damage',
      'admin.stat.dealt':         'Total dealt',
      'admin.stat.goal':          'Goal',
      'admin.empty.title':        'No event created yet',
      'admin.empty.hint':         'Click "Create new event" on the right to begin.',
      'admin.no_teams.title':     'No teams configured yet',
      'admin.no_teams.hint':      'Create an event to generate teams and invite links.',
      'admin.live_log':           'Live log',
      'admin.log.empty':          'No damage entries yet',
      'admin.controls':           'Event controls',
      'admin.new_event_btn':      '＋ Create new event',
      'admin.adjust_goal':        'Adjust damage goal',
      'admin.set':                'Set',
      'admin.pause':              '⏸ Pause',
      'admin.resume':             '▶ Resume',
      'admin.reset':              '↻ Reset',
      'admin.event_invite':       'Event invite',
      'admin.event_invite_hint':  'General link — streamer is registered without a team.',
      'admin.obs_browser':        'OBS browser source',
      'admin.obs_browser_hint':   'Add this URL as a browser source in OBS (300x180px, transparent).',
      'admin.howto':              'How it works',
      'admin.howto.1':            'Copy the team invite link and send it to your streamer.',
      'admin.howto.2':            'Streamer opens <code>DamageRace.exe</code>, picks "Join an event", enters code + WoT name.',
      'admin.howto.3':            'The app installs the WoT mod automatically.',
      'admin.howto.4':            'Add the OBS browser source with the URL above.',
      'admin.team.damage':        'Damage',
      'admin.team.remaining':     'Remaining',
      'admin.team.members':       'Members',
      'admin.team.no_members':    'No members — add a streamer or drag one in',
      'admin.team.add_streamer_ph': 'WoT name + Enter',
      'admin.team.remove_streamer': 'Remove streamer',
      'admin.team.join_self':      'Join me',
      'admin.team.join_self_title': 'Assign yourself to this team',
      'admin.team.join_self_prompt': 'Your WoT account name? (saved locally)',
      'admin.team.chip_title':     'Show streamer token',
      'admin.team.unassigned':     'Unassigned (drag onto a team to assign)',
      'admin.team.add_team':       'Add team',
      'admin.team.add_team_prompt':'Name for the new team:',
      'admin.team.remove_team':    'Remove team',
      'admin.team.remove_confirm': 'Remove team "{name}"? Members keep their tokens and become unassigned — you can drag them into another team afterwards.',
      'admin.team.rename_title':   'Rename team',
      'admin.team.rename_prompt':  'New team name:',
      'admin.adjust_mode':         'Mode',
      'admin.toast.mode_updated':  'Mode changed.',
      'admin.toast.team_added':    'Team added.',
      'admin.toast.team_removed':  'Team removed.',
      'admin.toast.team_renamed':  'Team renamed.',
      'admin.counting':            'Counting',
      'admin.counting_hint':       'Which damage types count towards the goal?',
      'admin.counting.direct':     'Direct damage',
      'admin.counting.assist':     'Assist (spot/track)',
      'admin.toast.counting_updated': 'Counting updated.',
      'admin.deadline':            'Deadline',
      'admin.deadline_hint':       'Time window for the goal. The event auto-pauses when it expires.',
      'admin.deadline_clear':      '✕ Clear deadline',
      'admin.deadline_none':       'No deadline set.',
      'admin.deadline_expired':    '⏱ Deadline expired.',
      'admin.deadline_in':         'Remaining: {time}',
      'admin.toast.deadline_updated': 'Deadline set.',
      'admin.toast.deadline_cleared': 'Deadline cleared.',
      'admin.toast.deadline_invalid': 'Deadline is invalid.',
      'admin.log.type_direct':     'Direct',
      'admin.log.type_assist':     'Assist',
      'admin.toast.joined_self':   'You joined the team.',
      'admin.token.title':         'Streamer token',
      'admin.token.hint':          'Paste this token into the WoT mod’s <code>config.json</code> at <code>res_mods/&lt;version&gt;/mods/damagerace/config.json</code>.',
      'admin.token.label_name':    'WoT name',
      'admin.token.label_token':   'Streamer token',
      'admin.token.label_config':  'Ready-made config.json',
      'admin.token.copy_config':   'Copy full config.json',
      'admin.token.install_btn':   '＞  Install mod now',
      'admin.token.install_prompt_path': 'WoT could not be auto-detected. Enter the full path (e.g. D:\\World_of_Tanks_EU):',
      'admin.token.missing':       'No token on file for this streamer.',
      'admin.toast.mod_installed': 'Mod installed (WoT {ver}). Launch the game — done.',
      'admin.toast.mod_no_wot':    'WoT installation not found.',
      'admin.toast.mod_install_failed': 'Mod install failed',
      'admin.confirm.remove_streamer': 'Really remove this streamer from the event?',
      'admin.toast.created':      'Event created.',
      'admin.toast.goal_updated': 'Goal updated.',
      'admin.toast.reset_done':   'Event reset.',
      'admin.toast.new_link':     'New invite link generated.',
      'admin.toast.streamer_added': 'Streamer added.',
      'admin.toast.streamer_moved': 'Streamer moved.',
      'admin.toast.streamer_removed': 'Streamer removed.',
      'admin.obs_add_btn':         '＋ Add to OBS',
      'admin.obs_password_prompt': 'OBS WebSocket password (OBS → Tools → WebSocket Server Settings):',
      'admin.toast.obs_added':     'Browser source added to OBS.',
      'admin.toast.obs_existed':   'Browser source already exists in OBS.',
      'admin.toast.obs_unreachable': 'OBS not reachable. Is the WebSocket Server enabled?',
      'admin.toast.obs_no_url':    'Overlay URL not available yet.',
      'admin.toast.obs_failed':    'OBS action failed',
      'common.save':               'Save',
      'admin.integrations':        'Integrations',
      'admin.integrations_hint':   'Discord webhook for the event recap. On event finish we post an embed with the winning team, top streamers and standings.',
      'admin.integrations.test':   'Test post',
      'admin.integrations.finish': '🏁 Finish & post',
      'admin.confirm.finish_event': 'Finish the event now and post the recap to Discord?',
      'admin.recap_posted_at':     'Recap already posted at {ts}',
      'admin.toast.discord_saved': 'Discord webhook saved.',
      'admin.toast.discord_cleared': 'Discord webhook cleared.',
      'admin.toast.discord_test_sent': 'Test post sent — check the Discord channel.',
      'admin.toast.event_finished': 'Event finished, recap posted.',
      'admin.toast.recap_already_posted': 'Recap was already posted.',
      'admin.wizard.title':       'Create new event',
      'admin.wizard.name':        'Event name',
      'admin.wizard.name_hint':   'e.g. Mohjos Summer Cup',
      'admin.wizard.goal':        'Damage goal',
      'admin.wizard.mode':        'Mode',
      'admin.wizard.mode_coop':   'Cooperative',
      'admin.wizard.mode_coop_d': 'All teams chase one shared goal',
      'admin.wizard.mode_versus': 'Versus',
      'admin.wizard.mode_v_desc': 'Team race: first team at the goal wins',
      'admin.wizard.teams':       'Teams (2-4)',
      'admin.wizard.add_team':    '＋ Add team',
      'admin.wizard.submit':      'Create event',

      'join.wrong':               'Invitation link is invalid',
      'join.wrong_hint':          'Please ask the organizer for a fresh link.',
      'join.invited_to':          'You are invited to',
      'join.assign_admin':        'General access — the organizer assigns your team',
      'join.wot_name':            'Your World of Tanks account name',
      'join.wot_placeholder':     'e.g. Mohjo_beist',
      'join.submit':              'Join',
      'join.submitting':          'Joining…',
      'join.after_info':          'After joining, install the <strong>DamageRace app</strong> (from your organizer) with the same name. Your damage will be tracked automatically.',
      'join.success_prefix':      '✓ Joined successfully',
      'join.team_suffix':         ' (Team {team})',
      'join.next_step':           '<strong>Next step:</strong> Download <strong>DamageRace.exe</strong> ({link}), open it, click "Join an event" and paste this code:',
      'join.releases_link':       'GitHub Releases',
      'join.error_failed':        'Could not join the event',
      'join.error_connection':    'Connection error.',
      'join.checking_link':       'Validating invite link…',
      'join.done':                'Done',

      'overlay.remaining':        'Remaining',
      'overlay.remaining_to_win': 'To win',
      'overlay.goal_reached':     '✓ Goal reached!',
      'overlay.paused':           '⏸ Paused',
      'overlay.expired':          '⏱ Time expired',
    },
  };

  function readCookie(name) {
    const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function writeCookie(name, value) {
    const oneYear = 60 * 60 * 24 * 365;
    document.cookie = name + '=' + encodeURIComponent(value) +
      '; path=/; max-age=' + oneYear + '; SameSite=Lax';
  }

  function detectInitial() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && SUPPORTED.indexOf(stored) >= 0) return stored;
    } catch (_) { /* localStorage unavailable */ }
    const cookie = readCookie(COOKIE_NAME);
    if (cookie && SUPPORTED.indexOf(cookie) >= 0) return cookie;
    const nav = (navigator.language || '').slice(0, 2).toLowerCase();
    if (SUPPORTED.indexOf(nav) >= 0) return nav;
    return DEFAULT_LANG;
  }

  let current = detectInitial();
  const listeners = [];

  function t(key, params) {
    const table = MESSAGES[current] || MESSAGES[DEFAULT_LANG];
    let value = table[key];
    if (value === undefined) value = key;
    if (params) {
      Object.keys(params).forEach(function (p) {
        value = value.replace(new RegExp('\\{' + p + '\\}', 'g'), params[p]);
      });
    }
    return value;
  }

  function apply(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach(function (el) {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    scope.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      el.innerHTML = t(el.getAttribute('data-i18n-html'));
    });
    scope.querySelectorAll('[data-i18n-attr]').forEach(function (el) {
      const spec = el.getAttribute('data-i18n-attr').split(',');
      spec.forEach(function (pair) {
        const parts = pair.split('=');
        if (parts.length === 2) {
          el.setAttribute(parts[0].trim(), t(parts[1].trim()));
        }
      });
    });
    document.documentElement.setAttribute('lang', current);
  }

  function set(lang) {
    if (SUPPORTED.indexOf(lang) < 0) return;
    current = lang;
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (_) {}
    writeCookie(COOKIE_NAME, lang);
    apply();
    listeners.forEach(function (fn) {
      try { fn(lang); } catch (_) {}
    });
  }

  function onChange(fn) { listeners.push(fn); }

  function mountToggle(host) {
    if (!host) return;
    host.classList.add('lang-toggle');
    host.innerHTML = '';
    SUPPORTED.forEach(function (code) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'lang-opt';
      btn.dataset.code = code;
      btn.textContent = code.toUpperCase();
      btn.addEventListener('click', function () { set(code); refreshToggle(host); });
      host.appendChild(btn);
    });
    refreshToggle(host);
  }

  function refreshToggle(host) {
    Array.prototype.forEach.call(host.querySelectorAll('.lang-opt'), function (btn) {
      btn.classList.toggle('active', btn.dataset.code === current);
    });
  }

  global.i18n = {
    t: t,
    apply: apply,
    set: set,
    get: function () { return current; },
    onChange: onChange,
    mountToggle: mountToggle,
    supported: SUPPORTED.slice(),
  };

  document.addEventListener('DOMContentLoaded', function () { apply(); });
})(window);
