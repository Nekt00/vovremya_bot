from __future__ import annotations

# Embedded HTML contains user-facing Russian copy and intentionally follows web formatting.
# ruff: noqa: E501, RUF001

MINI_APP_HTML = r"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#0B6174">
  <title>Вовремя</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      color-scheme: light dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --bg: var(--tg-theme-bg-color, #f4f5f7);
      --surface: var(--tg-theme-secondary-bg-color, #ffffff);
      --text: var(--tg-theme-text-color, #17212b);
      --theme-muted: var(--tg-theme-hint-color, #707b86);
      --theme-link: var(--tg-theme-link-color, #168acd);
      --button: var(--tg-theme-button-color, #0b6789);
      --button-text: var(--tg-theme-button-text-color, #ffffff);
      --muted: color-mix(in srgb, var(--theme-muted) 65%, var(--text));
      --link: color-mix(in srgb, var(--theme-link) 68%, var(--text));
      --separator: color-mix(in srgb, var(--muted) 22%, transparent);
      --success: color-mix(in srgb, #2d9b58 68%, var(--text));
      --danger: color-mix(in srgb, #cf4b4b 68%, var(--text));
      --warning: color-mix(in srgb, #b2720b 62%, var(--text));
      --control-border: color-mix(in srgb, var(--muted) 68%, var(--surface));
      --focus-ring: var(--link);
      --focus-surface: color-mix(in srgb, var(--surface) 92%, var(--button));
      --focus-shadow: 0 14px 34px rgb(0 0 0 / .10);
      --nav-shadow: 0 10px 30px rgb(0 0 0 / .16);
      --content-width: 560px;
      --bottom-nav-height: 70px;
      --control-height: 44px;
      --control-radius: 9px;
      --compact-action-width: 112px;
    }

    * { box-sizing: border-box; }

    .icon-sprite {
      position: absolute;
      width: 0;
      height: 0;
      overflow: hidden;
    }

    html { background: var(--bg); }

    body {
      min-width: 280px;
      margin: 0;
      background: linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface) 32%, var(--bg)) 0,
        var(--bg) 22rem
      );
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }

    ::selection { background: color-mix(in srgb, var(--button) 24%, transparent); }

    button, input, select { font: inherit; }

    button:focus-visible {
      outline: 3px solid var(--focus-ring);
      outline-offset: 2px;
    }

    .shell {
      width: min(100%, var(--content-width));
      min-height: 100dvh;
      margin: 0 auto;
      padding:
        max(14px, var(--tg-content-safe-area-inset-top, 0px), env(safe-area-inset-top))
        max(14px, var(--tg-content-safe-area-inset-right, 0px), env(safe-area-inset-right))
        calc(var(--bottom-nav-height) + 20px + max(var(--tg-content-safe-area-inset-bottom, 0px), env(safe-area-inset-bottom)))
        max(14px, var(--tg-content-safe-area-inset-left, 0px), env(safe-area-inset-left));
    }

    .app-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 44px;
      margin-bottom: 18px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 9px;
      min-width: 0;
      font-size: 15px;
      font-weight: 720;
      letter-spacing: -0.01em;
    }

    .brand-mark {
      display: grid;
      width: 30px;
      height: 30px;
      flex: none;
      place-items: center;
      color: var(--button);
    }

    .brand-mark svg {
      width: 30px;
      height: 30px;
      border-radius: 8px;
    }

    .timezone-label {
      overflow: hidden;
      color: var(--muted);
      font-size: 12px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .header-actions {
      display: flex;
      min-width: 0;
      align-items: center;
      gap: 8px;
    }

    .settings-button {
      display: grid;
      width: 44px;
      height: 44px;
      flex: none;
      place-items: center;
      border: 0;
      border-radius: 9px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
    }

    .settings-button svg { width: 21px; height: 21px; }

    .settings-button[aria-pressed="true"] {
      background: var(--surface);
      color: var(--text);
    }

    h1, h2, p { margin-top: 0; }

    h1 {
      margin-bottom: 5px;
      font-size: 26px;
      line-height: 1.18;
      letter-spacing: -0.025em;
    }

    h2 {
      margin-bottom: 10px;
      font-size: 15px;
      line-height: 1.3;
    }

    .lead, .section-note, .empty-copy, .setup-copy {
      color: var(--muted);
      line-height: 1.45;
    }

    .lead { margin-bottom: 18px; font-size: 14px; }

    .global-status {
      min-height: 20px;
      margin: -8px 0 10px;
      color: var(--muted);
      font-size: 13px;
    }

    .global-status:empty { display: none; }
    .global-status.error { color: var(--danger); }

    .day-overview {
      margin: 0 0 24px;
      padding: 20px;
      border-radius: 16px;
      background: linear-gradient(
        135deg,
        var(--focus-surface),
        var(--surface) 74%
      );
      box-shadow: var(--focus-shadow);
    }

    .next-intake-head {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 14px;
    }

    .next-intake-copy { min-width: 0; }

    .next-intake-label {
      display: block;
      margin-bottom: 5px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }

    .next-intake {
      margin: 0;
      overflow-wrap: anywhere;
      font-size: clamp(20px, 5.6vw, 24px);
      font-weight: 740;
      letter-spacing: -.025em;
      line-height: 1.25;
    }

    .next-intake-detail {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    .next-intake-action {
      width: var(--compact-action-width);
      min-height: var(--control-height);
      flex: none;
      padding: 8px 12px;
      border: 0;
      border-radius: 11px;
      background: var(--button);
      color: var(--button-text);
      cursor: pointer;
      font-weight: 700;
      transition: transform 120ms ease, opacity 160ms ease;
    }

    .next-intake-action:disabled { cursor: wait; opacity: .55; }
    .next-intake-action:not(:disabled):active { transform: scale(.98); }

    .day-progress {
      margin-top: 18px;
      padding-top: 15px;
      border-top: 1px solid var(--separator);
    }

    .progress-head {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 14px;
    }

    .progress-label {
      display: block;
      margin-bottom: 3px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
    }

    .progress-value {
      display: block;
      font-size: 15px;
      font-variant-numeric: tabular-nums;
      font-weight: 740;
      letter-spacing: -.02em;
      line-height: 1.2;
    }

    .progress-percent {
      color: var(--muted);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
      font-weight: 650;
    }

    .progress-track {
      height: 5px;
      margin-top: 9px;
      overflow: hidden;
      border-radius: 999px;
      background: color-mix(in srgb, var(--muted) 16%, transparent);
    }

    .progress-bar {
      width: 0;
      height: 100%;
      border-radius: inherit;
      background: var(--button);
      transition: width 180ms ease;
    }

    .tabs {
      position: fixed;
      z-index: 20;
      right: max(var(--tg-safe-area-inset-right, 0px), env(safe-area-inset-right));
      bottom: max(var(--tg-safe-area-inset-bottom, 0px), env(safe-area-inset-bottom));
      left: max(var(--tg-safe-area-inset-left, 0px), env(safe-area-inset-left));
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      width: min(calc(100% - 24px), calc(var(--content-width) - 12px));
      min-height: var(--bottom-nav-height);
      margin: 0 auto 10px;
      padding: 6px;
      border: 1px solid color-mix(in srgb, var(--button) 18%, var(--surface));
      border-radius: 18px;
      background: var(--surface);
      box-shadow: var(--nav-shadow);
      isolation: isolate;
    }

    .tab-indicator {
      position: absolute;
      z-index: 0;
      top: 6px;
      bottom: 6px;
      left: 6px;
      width: calc((100% - 12px) / 4);
      border-radius: 12px;
      background: var(--button);
      box-shadow: 0 7px 18px color-mix(in srgb, var(--button) 24%, transparent);
      pointer-events: none;
      will-change: left, width;
    }

    .tab {
      position: relative;
      z-index: 1;
      display: grid;
      min-width: 0;
      min-height: 56px;
      place-content: center;
      justify-items: center;
      gap: 2px;
      border: 0;
      border-radius: 12px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font-size: 11px;
      font-weight: 650;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
      transition: color 120ms ease-out;
      user-select: none;
    }

    .tab:focus:not(:focus-visible) { outline: none; }

    .tab svg {
      width: 20px;
      height: 20px;
      fill: none;
      stroke: currentColor;
      transition: transform 120ms ease-out, color 120ms ease-out;
    }

    .tab[aria-current="page"] {
      color: var(--button-text);
      font-weight: 720;
    }

    .tab[aria-current="page"] svg { transform: scale(1.06); }

    .section-head {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
    }

    .section-head h2 { margin-bottom: 0; font-size: 17px; }
    .section-note { margin: 0; font-size: 13px; }

    .section-actions {
      display: grid;
      grid-auto-columns: var(--compact-action-width);
      grid-auto-flow: column;
      flex: none;
      align-items: center;
      gap: 7px;
    }

    .compact-primary, .text-button {
      min-height: var(--control-height);
      border: 0;
      border-radius: var(--control-radius);
      cursor: pointer;
      font-weight: 670;
    }

    .compact-primary {
      width: 100%;
      padding: 8px 13px;
      background: var(--button);
      color: var(--button-text);
    }

    .text-button {
      padding: 7px 4px;
      background: transparent;
      color: var(--link);
    }

    .period-switch {
      display: inline-flex;
      flex: none;
      gap: 2px;
      padding: 2px;
      border: 1px solid var(--control-border);
      border-radius: 9px;
    }

    .period-button {
      min-width: 46px;
      min-height: var(--control-height);
      padding: 5px 10px;
      border: 0;
      border-radius: calc(var(--control-radius) - 2px);
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font-size: 13px;
      font-weight: 650;
    }

    .period-button[aria-pressed="true"] {
      background: var(--surface);
      color: var(--text);
    }

    .event-list {
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .set-group {
      margin-inline: -10px;
      padding: 17px 10px 4px;
      border-bottom: 1px solid var(--separator);
      border-radius: 11px;
      transition: background-color 160ms ease;
    }

    .set-group:last-child { border-bottom: 0; }

    .set-group.current {
      border-bottom-color: transparent;
      background: color-mix(in srgb, var(--button) 8%, transparent);
    }

    .set-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 3px;
    }

    .set-title {
      display: flex;
      margin: 0;
      align-items: center;
      gap: 7px;
      font-size: 16px;
      line-height: 1.35;
    }

    .schedule-icon {
      display: inline-grid;
      width: 20px;
      height: 20px;
      flex: none;
      place-items: center;
      color: var(--link);
    }

    .schedule-icon svg { width: 20px; height: 20px; fill: none; stroke: currentColor; }
    .set-window { margin: 2px 0 0; color: var(--muted); font-size: 12px; }

    .current-label {
      margin-left: 5px;
      color: var(--link);
      font-size: 11px;
      font-weight: 680;
      white-space: nowrap;
    }

    .set-take-button {
      width: var(--compact-action-width);
      min-height: var(--control-height);
      flex: none;
      padding: 8px 12px;
      border: 0;
      border-radius: var(--control-radius);
      background: var(--button);
      color: var(--button-text);
      cursor: pointer;
      font-weight: 670;
    }

    .set-take-button:disabled { cursor: wait; opacity: .55; }

    .set-events { margin: 0; padding: 0; list-style: none; }
    .set-events .event-row:last-child { border-bottom: 0; }
    .event-row.grouped { grid-template-columns: minmax(0, 1fr); padding-block: 12px; }

    .event-row {
      display: grid;
      grid-template-columns: 48px minmax(0, 1fr);
      gap: 12px;
      padding: 14px 0;
      border-bottom: 1px solid var(--separator);
    }

    .event-time {
      padding-top: 2px;
      font-size: 14px;
      font-variant-numeric: tabular-nums;
      font-weight: 690;
    }

    .event-main { min-width: 0; }

    .event-title-line {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
    }

    .event-name {
      display: flex;
      min-width: 0;
      align-items: center;
      gap: 9px;
      overflow-wrap: anywhere;
      font-size: 16px;
      font-weight: 680;
      line-height: 1.35;
    }

    .med-icon {
      display: grid;
      width: 26px;
      height: 26px;
      flex: none;
      place-items: center;
      border-radius: 8px;
      background: color-mix(in srgb, var(--button) 10%, transparent);
      color: var(--link);
    }

    .med-icon svg { width: 17px; height: 17px; fill: none; stroke: currentColor; }
    .med-name-copy { min-width: 0; overflow-wrap: anywhere; }

    .event-dose {
      margin: 3px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    .status-badge {
      flex: none;
      padding: 3px 7px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--muted) 11%, transparent);
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      line-height: 1.35;
      white-space: nowrap;
    }

    .status-badge.taken { background: color-mix(in srgb, var(--muted) 10%, transparent); color: var(--muted); }
    .status-badge.due, .status-badge.snoozed { background: color-mix(in srgb, var(--warning) 13%, transparent); color: var(--warning); }
    .status-badge.skipped, .status-badge.missed { background: color-mix(in srgb, var(--danger) 11%, transparent); color: var(--danger); }

    .event-row.is-complete .event-name,
    .event-row.is-complete .event-dose { color: var(--muted); }

    .event-row.is-complete .event-name { font-weight: 600; }
    .event-row.is-complete .med-icon { background: transparent; color: var(--muted); }

    .event-actions {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }

    .event-actions.corrective {
      justify-content: flex-end;
      margin-top: 8px;
    }

    .event-actions.corrective .action-button {
      border: 1px solid var(--control-border);
      background: transparent;
      color: var(--link);
    }

    .snooze-options {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 7px;
      margin-top: 8px;
    }

    .snooze-option {
      min-height: var(--control-height);
      padding: 7px 8px;
      border: 1px solid var(--control-border);
      border-radius: var(--control-radius);
      background: var(--surface);
      color: var(--text);
      cursor: pointer;
      font-size: 13px;
      font-weight: 650;
    }

    .action-button, .primary-button, .retry-button {
      min-height: var(--control-height);
      border: 0;
      border-radius: var(--control-radius);
      cursor: pointer;
      font-weight: 670;
    }

    .action-button { width: 100%; padding: 9px 12px; }
    .primary-button { background: var(--button); color: var(--button-text); }
    .action-button.take { border: 1px solid var(--control-border); background: var(--surface); color: var(--link); }
    .action-button.skip { background: transparent; color: var(--muted); }
    .action-button.snooze { border: 1px solid var(--control-border); background: transparent; color: var(--text); }
    .action-button:disabled, .primary-button:disabled, .retry-button:disabled { cursor: wait; opacity: .55; }

    .regimen-list {
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .regimen-jump-nav {
      display: flex;
      gap: 7px;
      margin: 14px 0 4px;
      overflow-x: auto;
      scrollbar-width: none;
    }

    .regimen-jump-nav::-webkit-scrollbar { display: none; }

    .regimen-jump-button {
      min-height: 38px;
      flex: 0 0 auto;
      padding: 7px 12px;
      border: 1px solid var(--control-border);
      border-radius: var(--control-radius);
      background: var(--surface);
      color: var(--text);
      cursor: pointer;
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
    }

    .regimen-group { scroll-margin-top: 14px; }
    .regimen-group + .regimen-group { margin-top: 22px; }

    .regimen-group-head {
      display: flex;
      align-items: center;
      gap: 9px;
      padding: 14px 0 9px;
      cursor: pointer;
      list-style: none;
    }

    .regimen-group-head::-webkit-details-marker { display: none; }
    .regimen-group-head .schedule-icon { color: var(--link); }
    .regimen-group-title { font-size: 15px; font-weight: 720; }
    .regimen-group-time { color: var(--muted); font-size: 12px; }
    .regimen-group-count {
      margin-left: auto;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
      font-weight: 650;
    }

    .regimen-group-head::after {
      width: 7px;
      height: 7px;
      flex: none;
      border-right: 2px solid var(--muted);
      border-bottom: 2px solid var(--muted);
      content: '';
      transform: rotate(45deg);
      transition: transform 160ms ease;
    }

    .regimen-group-details[open] > .regimen-group-head::after { transform: rotate(225deg); }

    .regimen-group-list {
      margin: 0;
      padding: 0;
      list-style: none;
      border-top: 1px solid var(--separator);
    }

    .regimen-row {
      padding: 16px 0;
      border-bottom: 1px solid var(--separator);
    }

    .regimen-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
    }

    .regimen-title {
      display: flex;
      min-width: 0;
      align-items: center;
      gap: 8px;
      overflow-wrap: anywhere;
      font-size: 16px;
      font-weight: 690;
      line-height: 1.35;
    }

    .regimen-properties {
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr);
      gap: 5px 10px;
      margin: 9px 0 0;
      font-size: 13px;
      line-height: 1.4;
    }

    .regimen-properties dt { color: var(--muted); }
    .regimen-properties dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }

    .regimen-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      gap: 8px;
      margin-top: 13px;
    }

    .regimen-actions > .regimen-button,
    .regimen-more { flex: 1 1 0; }

    .regimen-more { position: relative; }
    .regimen-more[open] { flex-basis: 100%; }
    .regimen-more > summary {
      display: grid;
      min-height: var(--control-height);
      place-items: center;
      border: 1px solid var(--control-border);
      border-radius: var(--control-radius);
      color: var(--muted);
      cursor: pointer;
      font-weight: 650;
      list-style: none;
    }
    .regimen-more > summary::-webkit-details-marker { display: none; }
    .regimen-more[open] > summary { color: var(--text); }
    .regimen-more-menu {
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }

    .regimen-button {
      display: inline-flex;
      width: 100%;
      min-height: var(--control-height);
      align-items: center;
      justify-content: center;
      gap: 7px;
      padding: 8px 12px;
      border: 1px solid var(--control-border);
      border-radius: var(--control-radius);
      background: transparent;
      color: var(--text);
      cursor: pointer;
      font-weight: 650;
    }

    .regimen-button.danger { color: var(--danger); }
    .regimen-button:disabled { cursor: wait; opacity: .55; }

    .family-section { margin-top: 22px; }
    .family-section h3 { margin: 0 0 8px; font-size: 15px; }
    .family-list {
      margin: 0;
      padding: 0;
      list-style: none;
      border-top: 1px solid var(--separator);
    }
    .family-row {
      display: flex;
      min-width: 0;
      padding: 13px 0;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--separator);
    }
    .family-row-main { min-width: 0; }
    .family-row-title {
      display: flex;
      align-items: center;
      gap: 8px;
      overflow-wrap: anywhere;
      font-size: 15px;
      font-weight: 680;
    }
    .family-row-meta { margin: 3px 0 0; color: var(--muted); font-size: 12px; line-height: 1.4; }
    .family-status-time { flex: none; color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
    .family-refresh svg { width: 18px; height: 18px; fill: none; stroke: currentColor; }
    .family-group { border-bottom: 1px solid var(--separator); }
    .family-group > .family-row { border-bottom: 0; }
    .family-members { margin: 0 0 8px 20px; padding: 0; list-style: none; }
    .family-members .family-row { padding: 9px 0; }
    .family-row.has-actions { display: grid; grid-template-columns: minmax(0, 1fr); }
    .family-actions {
      display: grid;
      width: 100%;
      grid-auto-columns: minmax(0, 1fr);
      grid-auto-flow: column;
      gap: 7px;
    }
    .family-action {
      width: 100%;
      min-height: var(--control-height);
      padding: 6px 9px;
      border: 1px solid var(--control-border);
      border-radius: var(--control-radius);
      background: transparent;
      color: var(--text);
      cursor: pointer;
      font-size: 12px;
      font-weight: 650;
    }
    .family-action.danger { color: var(--danger); }
    .family-action:disabled { cursor: wait; opacity: .5; }

    .family-dialog {
      width: min(calc(100% - 28px), 420px);
      padding: 0;
      border: 0;
      border-radius: 16px;
      background: var(--surface);
      color: var(--text);
      box-shadow: 0 20px 60px color-mix(in srgb, #000 28%, transparent);
    }
    .family-dialog::backdrop { background: rgb(0 0 0 / .36); }
    .family-dialog-form { display: grid; gap: 14px; padding: 20px; }
    .family-dialog-form h2 { margin: 0; font-size: 19px; }
    .family-dialog-form label { display: grid; gap: 7px; color: var(--muted); font-size: 13px; }
    .family-dialog-form input, .family-dialog-form select {
      width: 100%;
      min-height: 46px;
      padding: 10px 12px;
      border: 1px solid var(--control-border);
      border-radius: 10px;
      background: var(--bg);
      color: var(--text);
    }
    .family-role-options { display: grid; gap: 8px; }
    .family-role-option {
      display: grid;
      grid-template-columns: auto 1fr;
      align-items: start;
      gap: 9px;
      padding: 10px;
      border: 1px solid var(--control-border);
      border-radius: 10px;
    }
    .family-role-option input { width: auto; min-height: auto; margin-top: 3px; }
    .family-role-option strong { display: block; color: var(--text); font-size: 13px; }
    .family-role-option small { display: block; margin-top: 3px; line-height: 1.35; }
    .family-dialog-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .status-badge.active { background: color-mix(in srgb, var(--success) 13%, transparent); color: var(--success); }
    .status-badge.paused { background: color-mix(in srgb, var(--warning) 13%, transparent); color: var(--warning); }
    .status-badge.completed { color: var(--muted); }

    .set-management-list {
      margin: 0;
      padding: 0;
      list-style: none;
      border-top: 1px solid var(--separator);
    }

    .managed-set-row {
      padding: 16px 0;
      border-bottom: 1px solid var(--separator);
    }

    .managed-set-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }

    .managed-set-title {
      display: flex;
      margin: 0;
      align-items: center;
      gap: 8px;
      font-size: 16px;
    }
    .managed-set-window { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
    .managed-set-members { margin: 11px 0 0; padding: 0; list-style: none; }
    .managed-set-members li {
      display: flex;
      padding: 3px 0;
      align-items: center;
      gap: 7px;
      font-size: 14px;
      line-height: 1.4;
    }

    .set-editor {
      display: grid;
      gap: 12px;
      margin-top: 15px;
      padding-top: 15px;
      border-top: 1px solid var(--separator);
    }

    .member-options { display: grid; gap: 7px; }

    .member-option {
      display: flex;
      min-height: 44px;
      align-items: center;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--control-border);
      border-radius: 9px;
      background: var(--surface);
      cursor: pointer;
    }

    .member-option input { width: 18px; height: 18px; flex: none; accent-color: var(--button); }
    .member-option-copy { min-width: 0; }
    .member-option-name {
      display: flex;
      align-items: center;
      gap: 7px;
      overflow-wrap: anywhere;
      font-size: 14px;
      font-weight: 650;
    }
    .member-option-dose { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; }
    .set-editor-actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .preset-section {
      display: grid;
      gap: 10px;
      margin-top: 22px;
    }

    .preset-actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }

    .settings-form {
      display: grid;
      gap: 22px;
      margin-top: 18px;
    }

    .settings-form > .primary-button { margin-top: 0; }

    .settings-section {
      display: grid;
      gap: 16px;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--separator);
    }

    .settings-section:last-of-type { border-bottom: 0; }

    .setting-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }

    .setting-copy { min-width: 0; }
    .setting-title { display: block; margin-bottom: 3px; font-size: 15px; font-weight: 680; }
    .setting-description { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.4; }

    .switch-control { position: relative; width: 50px; height: 30px; flex: none; }
    .switch-control input { position: absolute; opacity: 0; pointer-events: none; }
    .switch-track {
      display: block;
      width: 100%;
      height: 100%;
      border: 1px solid var(--control-border);
      border-radius: 999px;
      background: color-mix(in srgb, var(--muted) 28%, transparent);
      cursor: pointer;
      transition: background 160ms ease;
    }

    .switch-track::after {
      content: "";
      position: absolute;
      top: 3px;
      left: 3px;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: var(--surface);
      box-shadow: 0 1px 3px color-mix(in srgb, var(--text) 20%, transparent);
      transition: transform 160ms ease;
    }

    .switch-control input:checked + .switch-track { background: var(--button); }
    .switch-control input:checked + .switch-track::after { transform: translateX(20px); }
    .switch-control input:focus-visible + .switch-track {
      outline: 3px solid var(--focus-ring);
      outline-offset: 2px;
    }

    .repeat-field { min-width: 0; margin: 0; padding: 0; border: 0; }
    .repeat-field:disabled { opacity: .5; }
    .repeat-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; margin-top: 9px; }

    .repeat-option { position: relative; }
    .repeat-option input { position: absolute; opacity: 0; pointer-events: none; }
    .repeat-option span {
      display: grid;
      min-height: 44px;
      place-items: center;
      border: 1px solid var(--control-border);
      border-radius: 9px;
      background: var(--surface);
      cursor: pointer;
      font-size: 14px;
      font-weight: 650;
    }

    .repeat-option input:checked + span {
      border-color: var(--button);
      background: color-mix(in srgb, var(--button) 12%, var(--surface));
      color: var(--link);
    }

    .repeat-option input:focus-visible + span {
      outline: 3px solid var(--focus-ring);
      outline-offset: 2px;
    }

    .timezone-value { font-size: 15px; font-weight: 680; overflow-wrap: anywhere; }
    .timezone-action { justify-self: start; }

    .date-heading {
      margin: 20px 0 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 690;
      letter-spacing: .035em;
      text-transform: uppercase;
    }

    .date-heading:first-child { margin-top: 12px; }

    .history-summary {
      margin: 12px 0 4px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    .history-summary:empty { display: none; }

    .history-planned-note {
      margin: 8px 0 2px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
    }

    .history-summary strong { color: var(--text); font-weight: 680; }

    .history-controls {
      display: grid;
      grid-template-columns: var(--compact-action-width) minmax(0, 1fr);
      align-items: center;
      gap: 7px;
    }

    .report-preview { display: grid; gap: 14px; }
    .report-metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .report-metric, .report-course {
      padding: 11px;
      border: 1px solid var(--separator);
      border-radius: 10px;
      background: var(--bg);
    }
    .report-metric span { display: block; color: var(--muted); font-size: 12px; }
    .report-metric strong { display: block; margin-top: 3px; font-size: 18px; }
    .report-course-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
    .report-course strong { display: block; font-size: 14px; }
    .report-course p { margin: 4px 0 0; font-size: 12px; line-height: 1.45; }
    .report-note { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }

    .today-intro {
      padding: 5px 2px 18px;
    }

    .today-heading {
      margin-bottom: 5px;
      font-size: 30px;
      letter-spacing: -.03em;
    }

    .today-heading + .lead { margin-bottom: 0; font-size: 14px; }

    .empty, .error-state, .setup, .loading-state {
      padding: 34px 18px;
      text-align: center;
    }

    .empty-icon, .setup-icon {
      display: grid;
      width: 48px;
      height: 48px;
      margin: 0 auto 12px;
      place-items: center;
      border-radius: 14px;
      background: color-mix(in srgb, var(--button) 10%, transparent);
      color: var(--link);
    }

    .empty-icon svg, .setup-icon svg { width: 26px; height: 26px; fill: none; stroke: currentColor; }
    .empty-title, .setup-title { margin-bottom: 6px; font-size: 18px; font-weight: 710; }
    .empty-copy, .setup-copy { max-width: 390px; margin: 0 auto; font-size: 14px; }

    .primary-button {
      width: 100%;
      margin-top: 20px;
      padding: 12px 16px;
    }

    .form-page-head {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
    }

    .form-page-head h1 { margin: 0; font-size: 21px; }

    .regimen-form {
      display: grid;
      gap: 22px;
    }

    .form-section {
      display: grid;
      gap: 13px;
      padding-bottom: 22px;
      border-bottom: 1px solid var(--separator);
    }

    .form-section:last-of-type { border-bottom: 0; padding-bottom: 0; }

    .form-section-title {
      margin: 0;
      font-size: 15px;
      line-height: 1.35;
    }

    .field {
      display: grid;
      gap: 6px;
    }

    .field-label {
      font-size: 13px;
      font-weight: 650;
    }

    .field-hint {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }

    .field input, .field select {
      width: 100%;
      min-height: 46px;
      padding: 10px 12px;
      border: 1px solid var(--control-border);
      border-radius: 9px;
      outline: none;
      background: var(--surface);
      color: var(--text);
    }

    .field input:focus, .field select:focus {
      border-color: var(--link);
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--link) 16%, transparent);
    }

    .field-row {
      display: grid;
      grid-template-columns: minmax(0, .8fr) minmax(0, 1.2fr);
      gap: 10px;
    }

    .choice-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .choice-option { position: relative; }
    .choice-option input { position: absolute; opacity: 0; pointer-events: none; }

    .choice-option > span {
      display: flex;
      min-height: 46px;
      align-items: center;
      justify-content: center;
      padding: 8px 10px;
      border: 1px solid var(--control-border);
      border-radius: 9px;
      background: var(--surface);
      cursor: pointer;
      font-size: 13px;
      font-weight: 650;
      text-align: center;
    }

    .choice-option .choice-copy {
      display: grid;
      gap: 3px;
      justify-items: center;
    }

    .choice-icon { width: 22px; height: 22px; fill: none; stroke: currentColor; }

    .choice-option input:checked + span {
      border-color: var(--button);
      background: color-mix(in srgb, var(--button) 12%, var(--surface));
      color: var(--link);
    }

    .choice-option input:focus-visible + span {
      outline: 3px solid var(--focus-ring);
      outline-offset: 2px;
    }

    .weekday-grid {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 5px;
    }

    .weekday-option { position: relative; }
    .weekday-option input { position: absolute; opacity: 0; pointer-events: none; }

    .weekday-option span {
      display: grid;
      min-height: 44px;
      place-items: center;
      border: 1px solid var(--control-border);
      border-radius: 8px;
      background: var(--surface);
      cursor: pointer;
      font-size: 12px;
      font-weight: 680;
    }

    .weekday-option input:checked + span {
      border-color: var(--button);
      background: var(--button);
      color: var(--button-text);
    }

    .form-error {
      margin: 0;
      color: var(--danger);
      font-size: 13px;
      line-height: 1.4;
    }

    .form-actions {
      position: sticky;
      bottom: max(0px, env(safe-area-inset-bottom));
      padding: 10px 0;
      background: var(--bg);
    }

    .form-actions .primary-button { margin: 0; }

    .retry-button {
      width: 100%;
      padding: 10px 16px;
      background: var(--surface);
      color: var(--text);
    }

    .skeleton {
      height: 70px;
      border-bottom: 1px solid var(--separator);
      background: color-mix(in srgb, var(--muted) 7%, transparent);
      animation: loading 1.3s ease-in-out infinite alternate;
    }

    [hidden] { display: none !important; }

    @keyframes loading { to { opacity: .4; } }

    @media (prefers-reduced-motion: reduce) {
      .skeleton { animation: none; }
      .switch-track, .switch-track::after, .progress-bar, .set-group,
      .next-intake-action, .tab, .tab svg, .regimen-group-head::after { transition: none; }
      .next-intake-action:not(:disabled):active,
      .tab[aria-current="page"] svg { transform: none; }
      html { scroll-behavior: auto; }
    }

    @media (max-width: 400px) {
      .shell { padding-inline: 12px; }
      .timezone-label { display: none; }
      .next-intake-head { align-items: stretch; flex-direction: column; }
      .next-intake-action { width: 100%; }
      .day-overview { padding: 18px; }
      .event-title-line { gap: 6px; }
      .event-name { font-size: 15px; }
      .status-badge { padding-inline: 5px; }
    }

    @media (max-width: 440px) {
      #regimens-panel .section-head { align-items: stretch; flex-direction: column; }
      #regimens-panel .section-actions { width: 100%; }
      #regimens-panel .section-actions { grid-auto-columns: minmax(0, 1fr); }
      #history-panel .section-head { align-items: stretch; flex-direction: column; }
      #history-panel .period-switch { width: 100%; }
      #history-panel .period-button { flex: 1; }
      #family-panel .section-head { align-items: stretch; flex-direction: column; }
      #family-panel .section-actions { width: 100%; }
      #family-panel .section-actions { grid-auto-columns: minmax(0, 1fr); }
      .managed-set-head { align-items: stretch; flex-direction: column; }
      .managed-set-head .section-actions {
        width: 100%;
        grid-auto-columns: minmax(0, 1fr);
      }
    }

    @media (min-width: 560px) {
      .shell { padding-inline: 24px; }
      .event-row { grid-template-columns: 58px minmax(0, 1fr); }
    }
  </style>
</head>
<body>
  <svg class="icon-sprite" aria-hidden="true">
    <defs>
      <symbol id="icon-gear" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915"/><circle cx="12" cy="12" r="3"/></symbol>
      <symbol id="icon-calendar-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 3H5"/><path d="M21 13V5"/><path d="M21 5a2 2 0 0 0-2-2"/><path d="M3 19a2 2 0 0 0 2 2"/><path d="M3 5v14"/><path d="M5 3a2 2 0 0 0-2 2"/><path d="m16 19 2 2 4-4"/><path d="M16 2v3"/><path d="M3 9h18"/><path d="M5 21h7.5"/><path d="M8 2v3"/></symbol>
      <symbol id="icon-clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6h4"/></symbol>
      <symbol id="icon-globe" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.54 15H17a2 2 0 0 0-2 2v4.54M7 3.34V5a3 3 0 0 0 3 3 2 2 0 0 1 2 2c0 1.1.9 2 2 2s2-.9 2-2 .9-2 2-2h3.17M11 21.95V18a2 2 0 0 0-2-2 2 2 0 0 1-2-2v-1a2 2 0 0 0-2-2H2.05"/><circle cx="12" cy="12" r="10"/></symbol>
      <symbol id="icon-pill" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7ZM8.5 8.5l7 7"/></symbol>
      <symbol id="icon-tablet" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="7" r="5"/><circle cx="17" cy="17" r="5"/><path d="M12 17h10M3.46 10.54l7.08-7.08"/></symbol>
      <symbol id="icon-syringe" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 2 4 4M17 7l3-3M19 9 8.7 19.3c-1 1-2.5 1-3.4 0l-.6-.6c-1-1-1-2.5 0-3.4L15 5M9 11l4 4M5 19l-3 3M14 4l6 6"/></symbol>
      <symbol id="icon-drop" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7Z"/></symbol>
      <symbol id="icon-sunrise" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v8m-7.07.93 1.41 1.41M2 18h2m16 0h2m-2.93-7.07-1.41 1.41M22 22H2m6-16 4-4 4 4M16 18a4 4 0 0 0-8 0"/></symbol>
      <symbol id="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></symbol>
      <symbol id="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></symbol>
      <symbol id="icon-history" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8M3 3v5h5M12 7v5l4 2"/></symbol>
      <symbol id="icon-clipboard" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M12 11h4m-4 5h4M8 11h.01M8 16h.01"/></symbol>
      <symbol id="icon-other" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 2v2M5 2v2M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1M8 15a6 6 0 0 0 12 0v-3"/><circle cx="20" cy="10" r="2"/></symbol>
      <symbol id="icon-users" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 21a8 8 0 0 0-16 0"/><circle cx="10" cy="8" r="5"/><path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"/></symbol>
      <symbol id="icon-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16M8 16H3v5"/></symbol>
    </defs>
  </svg>
  <main class="shell">
    <header class="app-header">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 256 256" fill="none">
            <rect width="256" height="256" rx="64" fill="#0B6174"/>
            <path d="M58 132 107 181" stroke="#AEE9D2" stroke-width="30" stroke-linecap="round"/>
            <path d="m106 181 93-106" stroke="#FFFFFF" stroke-width="30" stroke-linecap="round"/>
            <circle cx="199" cy="75" r="10" fill="#FF8E72"/>
          </svg>
        </span>
        <span>Вовремя</span>
      </div>
      <div class="header-actions">
        <span class="timezone-label" id="timezone-label"></span>
        <button class="settings-button" id="settings-button" type="button" aria-label="Настройки" aria-pressed="false" hidden>
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><use href="#icon-gear"/></svg>
        </button>
      </div>
    </header>

    <p class="global-status" id="global-status" role="status" aria-live="polite"></p>

    <section class="loading-state" id="loading-state" aria-label="Загрузка">
      <div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>
    </section>

    <section class="error-state" id="error-state" hidden>
      <div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#icon-history"/></svg></div>
      <h1>Не удалось загрузить данные</h1>
      <p class="empty-copy" id="error-copy">Проверьте соединение и попробуйте ещё раз.</p>
      <button class="retry-button" id="retry-button" type="button">Повторить</button>
    </section>

    <section class="setup" id="setup-state" hidden>
      <div class="setup-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#icon-globe"/></svg></div>
      <h1 class="setup-title">Подтвердите часовой пояс</h1>
      <p class="setup-copy" id="zone">Определяем часовой пояс…</p>
      <button class="primary-button" id="save-timezone" type="button">Использовать этот часовой пояс</button>
    </section>

    <div id="app-content" hidden>
      <section id="today-panel" aria-labelledby="today-tab">
        <header class="today-intro">
          <h1 class="today-heading" id="today-title" tabindex="-1">Сегодня</h1>
          <p class="lead" id="today-date"></p>
        </header>

        <section class="day-overview" id="dashboard-summary" aria-label="Прогресс на сегодня">
          <div class="next-intake-head">
            <div class="next-intake-copy">
              <span class="next-intake-label" id="next-intake-label">Следующий приём</span>
              <p class="next-intake" id="next-intake"></p>
              <p class="next-intake-detail" id="next-intake-detail"></p>
            </div>
            <button class="next-intake-action" id="next-intake-action" type="button" hidden></button>
          </div>
          <div class="day-progress">
            <div class="progress-head">
              <div>
                <span class="progress-label">Выполнено сегодня</span>
                <strong class="progress-value" id="daily-progress">0 из 0</strong>
              </div>
              <span class="progress-percent" id="daily-progress-percent">0%</span>
            </div>
            <div class="progress-track" id="daily-progress-track" role="progressbar" aria-label="Выполненные приёмы" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0">
              <div class="progress-bar" id="daily-progress-bar"></div>
            </div>
          </div>
        </section>

        <ul class="event-list" id="today-list"></ul>
        <p class="history-summary" id="next-scheduled-intake"></p>
        <button class="primary-button" id="edit-intakes-button" type="button">Отметить приём вручную</button>
      </section>

      <dialog class="family-dialog" id="intake-editor-dialog" aria-labelledby="intake-editor-title">
        <div class="family-dialog-form">
          <h2 id="intake-editor-title">Отметить приём · Сегодня</h2>
          <p class="report-note">Нажмите на препарат, чтобы изменить статус. Повторное нажатие вернёт его обратно. После отмены напоминание придёт в запланированное время своего набора.</p>
          <ul class="event-list" id="intake-editor-list"></ul>
          <button class="compact-primary" id="intake-editor-close" type="button">Готово</button>
        </div>
      </dialog>

      <section id="history-panel" aria-labelledby="history-tab" hidden>
        <div class="section-head">
          <div><h2 id="history-title" tabindex="-1">История приёмов</h2><p class="section-note">По местному времени</p></div>
          <div class="history-controls">
            <button class="regimen-button" id="open-report-button" type="button">Отчёт</button>
            <div class="period-switch" aria-label="Период истории">
              <button class="period-button" type="button" data-days="7" aria-pressed="true">7 дней</button>
              <button class="period-button" type="button" data-days="30" aria-pressed="false">30 дней</button>
            </div>
          </div>
        </div>
        <p class="history-summary" id="history-summary"></p>
        <p class="history-planned-note" id="history-planned-note" hidden>Запланированные приёмы можно отметить вручную.</p>
        <div id="history-list"></div>
        <div class="empty" id="history-empty" hidden>
          <div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#icon-clipboard"/></svg></div>
          <p class="empty-title">История пока пуста</p>
          <p class="empty-copy">Здесь появятся выполненные и пропущенные приёмы.</p>
        </div>
      </section>

      <section id="regimens-panel" aria-labelledby="regimens-tab" hidden>
        <div class="section-head">
          <div><h2 id="regimens-title" tabindex="-1">Мои курсы</h2><p class="section-note">Графики и состояние курсов</p></div>
          <div class="section-actions">
            <button class="regimen-button" id="manage-sets-button" type="button">Наборы</button>
            <button class="compact-primary" id="add-regimen-button" type="button">Добавить</button>
          </div>
        </div>
        <nav class="regimen-jump-nav" id="regimen-jump-nav" aria-label="Быстрый переход по времени" hidden></nav>
        <ul class="regimen-list" id="regimen-list"></ul>
        <div class="loading-state" id="regimens-loading" hidden>
          <div class="skeleton"></div><div class="skeleton"></div>
        </div>
        <div class="empty" id="regimens-empty" hidden>
          <div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#icon-pill"/></svg></div>
          <p class="empty-title">Курсов пока нет</p>
          <p class="empty-copy">Добавьте препарат, дозировку и время напоминаний.</p>
          <button class="primary-button" id="empty-add-regimen-button" type="button">Добавить курс</button>
        </div>
      </section>

      <section id="family-panel" aria-labelledby="family-tab" hidden>
        <div class="section-head">
          <div><h2 id="family-title" tabindex="-1">Семья</h2><p class="section-note">Приёмы близких по вашим курсам</p></div>
          <div class="section-actions" id="family-actions">
            <button class="regimen-button family-refresh" id="refresh-family-button" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-refresh"/></svg>
              <span>Обновить</span>
            </button>
            <button class="compact-primary" id="invite-family-button" type="button">Добавить</button>
          </div>
        </div>
        <div class="loading-state" id="family-loading" hidden>
          <div class="skeleton"></div><div class="skeleton"></div>
        </div>
        <div id="family-content" hidden>
          <section class="family-section" aria-labelledby="family-groups-title">
            <h3 id="family-groups-title">Группы и участники</h3>
            <ul class="family-list" id="family-groups-list"></ul>
          </section>
          <section class="family-section" id="family-today-section" aria-labelledby="family-today-title">
            <h3 id="family-today-title">Сегодня</h3>
            <p class="history-summary" id="family-today-summary"></p>
            <ul class="family-list" id="family-today-list"></ul>
          </section>
          <section class="family-section" id="family-assignments-section" aria-labelledby="family-assignments-title">
            <h3 id="family-assignments-title">Курсы</h3>
            <ul class="family-list" id="family-assignments-list"></ul>
          </section>
        </div>
        <div class="empty" id="family-empty" hidden>
          <div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#icon-users"/></svg></div>
          <p class="empty-title">Семейной группы пока нет</p>
          <p class="empty-copy">Создайте группу и отправьте близкому одноразовую ссылку.</p>
          <button class="primary-button" id="empty-invite-family-button" type="button">Добавить близкого</button>
        </div>
      </section>

      <dialog class="family-dialog" id="family-dialog">
        <form class="family-dialog-form" id="family-dialog-form" method="dialog">
          <h2 id="family-dialog-title">Изменить</h2>
          <label><span id="family-dialog-label">Название</span><input id="family-dialog-input" maxlength="64" required autocomplete="off"></label>
          <div class="family-dialog-actions">
            <button class="regimen-button" id="family-dialog-cancel" type="button">Отмена</button>
            <button class="compact-primary" value="save">Сохранить</button>
          </div>
        </form>
      </dialog>

      <dialog class="family-dialog" id="family-invite-dialog">
        <form class="family-dialog-form" id="family-invite-form" method="dialog">
          <h2>Пригласить участника</h2>
          <label>Группа<select id="family-invite-group"></select></label>
          <label id="family-new-group-field">Название новой группы<input id="family-new-group-name" maxlength="64" autocomplete="off"></label>
          <label>Имя участника<input id="family-invite-name" maxlength="64" autocomplete="off" required></label>
          <div class="family-role-options" role="radiogroup" aria-label="Роль участника">
            <label class="family-role-option">
              <input type="radio" name="family_role" value="dependent" checked>
              <span><strong>Только отмечать приёмы</strong><small>Не сможет создавать и менять курсы.</small></span>
            </label>
            <label class="family-role-option">
              <input type="radio" name="family_role" value="self_managed">
              <span><strong>Добавлять свои приёмы</strong><small>Курсы владельца останутся защищены.</small></span>
            </label>
          </div>
          <div class="family-dialog-actions">
            <button class="regimen-button" id="family-invite-cancel" type="button">Отмена</button>
            <button class="compact-primary" value="save">Создать ссылку</button>
          </div>
        </form>
      </dialog>

      <dialog class="family-dialog" id="report-dialog">
        <form class="family-dialog-form" id="report-form">
          <h2>Отчёт о приёме</h2>
          <label>Период
            <select name="period" id="report-period">
              <option value="7">7 дней</option>
              <option value="30" selected>30 дней</option>
              <option value="90">90 дней</option>
              <option value="all">Весь курс</option>
            </select>
          </label>
          <label>Курс
            <select name="regimen_id" id="report-regimen">
              <option value="">Все препараты</option>
            </select>
          </label>
          <p class="form-error" id="report-error" role="alert" tabindex="-1" hidden></p>
          <div class="report-preview" id="report-preview" hidden>
            <div class="report-metrics" id="report-metrics"></div>
            <ul class="report-course-list" id="report-course-list"></ul>
            <p class="report-note" id="report-note"></p>
          </div>
          <div class="family-dialog-actions">
            <button class="regimen-button" id="report-cancel" type="button">Закрыть</button>
            <button class="compact-primary" id="report-generate" type="submit">Показать</button>
          </div>
          <button class="primary-button" id="report-download" type="button" hidden>Скачать PDF</button>
        </form>
      </dialog>

      <section id="sets-panel" aria-labelledby="sets-title" hidden>
        <div class="form-page-head">
          <button class="text-button" id="cancel-sets" type="button" aria-label="Вернуться к курсам">← Назад</button>
          <h1 id="sets-title">Наборы</h1>
        </div>
        <p class="lead">Объедините препараты, которые принимаете одновременно.</p>
        <div class="loading-state" id="sets-loading" hidden>
          <div class="skeleton"></div><div class="skeleton"></div>
        </div>
        <ul class="set-management-list" id="set-management-list"></ul>
        <div class="empty" id="sets-empty" hidden>
          <div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><use href="#icon-sunrise"/></svg></div>
          <p class="empty-title">Наборов пока нет</p>
          <p class="empty-copy">Создайте набор и выберите препараты для общего напоминания.</p>
        </div>
        <section class="preset-section" id="preset-section" aria-labelledby="preset-title">
          <h2 id="preset-title">Создать набор</h2>
          <div class="preset-actions" id="preset-actions"></div>
          <div id="new-set-editor"></div>
        </section>
        <p class="form-error" id="sets-error" role="alert" tabindex="-1" hidden></p>
      </section>

      <section id="settings-panel" aria-labelledby="settings-title" hidden>
        <h1 id="settings-title">Настройки</h1>
        <p class="lead">Уведомления и местное время</p>

        <form class="settings-form" id="settings-form">
          <section class="settings-section" aria-labelledby="notifications-title">
            <div class="setting-row">
              <div class="setting-copy">
                <span class="setting-title" id="notifications-title">Напоминания</span>
                <p class="setting-description">Повторяются, пока приём не будет отмечен.</p>
              </div>
              <label class="switch-control">
                <input id="reminders-enabled" name="reminders_enabled" type="checkbox" role="switch" aria-labelledby="notifications-title">
                <span class="switch-track" aria-hidden="true"></span>
              </label>
            </div>

            <fieldset class="repeat-field" id="repeat-field">
              <legend class="setting-title">Интервал повтора</legend>
              <p class="setting-description">Как часто напоминать о неотмеченном приёме.</p>
              <div class="repeat-options">
                <label class="repeat-option"><input type="radio" name="repeat_minutes" value="15"><span>15 мин</span></label>
                <label class="repeat-option"><input type="radio" name="repeat_minutes" value="30"><span>30 мин</span></label>
                <label class="repeat-option"><input type="radio" name="repeat_minutes" value="60"><span>60 мин</span></label>
              </div>
            </fieldset>
          </section>

          <section class="settings-section" aria-labelledby="timezone-settings-title">
            <div>
              <span class="setting-title" id="timezone-settings-title">Часовой пояс</span>
              <div class="timezone-value" id="settings-timezone"></div>
              <p class="setting-description" id="detected-timezone-note"></p>
            </div>
            <button class="regimen-button timezone-action" id="update-timezone-button" type="button" hidden></button>
          </section>

          <p class="form-error" id="settings-error" role="alert" tabindex="-1" hidden></p>
          <button class="primary-button" id="save-settings-button" type="submit">Сохранить настройки</button>
        </form>
      </section>

      <section id="regimen-create-panel" aria-labelledby="regimen-create-title" hidden>
        <div class="form-page-head">
          <button class="text-button" id="cancel-regimen-create" type="button" aria-label="Вернуться к курсам">← Назад</button>
          <h1 id="regimen-create-title">Новый курс</h1>
        </div>
        <p class="section-note" id="regimen-edit-note" hidden>Изменения затронут только будущие приёмы. История останется без изменений.</p>

        <form class="regimen-form" id="regimen-create-form">
          <section class="form-section" aria-labelledby="medicine-section-title">
            <h2 class="form-section-title" id="medicine-section-title">Препарат и дозировка</h2>
            <label class="field">
              <span class="field-label">Название препарата</span>
              <input name="medication_name" type="text" maxlength="120" autocomplete="off" placeholder="Например, Витамин D3" required>
            </label>
            <label class="field">
              <span class="field-label">Форма</span>
              <select name="medication_form" id="create-medication-form">
                <option value="tablet">Таблетка</option>
                <option value="capsule">Капсула</option>
                <option value="injection">Укол</option>
                <option value="drops">Капли</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <div class="field-row">
              <label class="field">
                <span class="field-label">Количество</span>
                <input name="dose_amount" type="text" inputmode="decimal" maxlength="32" placeholder="1" required>
              </label>
              <label class="field">
                <span class="field-label">Единица</span>
                <input name="dose_unit" id="create-dose-unit" type="text" list="dose-unit-options" maxlength="32" placeholder="таблетка" required>
                <datalist id="dose-unit-options"></datalist>
              </label>
            </div>
            <label class="field">
              <span class="field-label">Связь с приёмом пищи</span>
              <select name="meal_timing">
                <option value="independent">Неважно</option>
                <option value="before">До еды</option>
                <option value="during">Во время еды</option>
                <option value="after">После еды</option>
              </select>
            </label>
          </section>

          <section class="form-section" aria-labelledby="reminder-section-title">
            <h2 class="form-section-title" id="reminder-section-title">Когда напоминать</h2>
            <div class="choice-grid" role="radiogroup" aria-label="Период напоминания">
              <label class="choice-option"><input type="radio" name="reminder_target" value="morning" required><span class="choice-copy"><svg class="choice-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-sunrise"/></svg><span>Утро<br>06–12</span></span></label>
              <label class="choice-option"><input type="radio" name="reminder_target" value="day"><span class="choice-copy"><svg class="choice-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-sun"/></svg><span>День<br>11–17</span></span></label>
              <label class="choice-option"><input type="radio" name="reminder_target" value="evening"><span class="choice-copy"><svg class="choice-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-moon"/></svg><span>Вечер<br>18–23</span></span></label>
              <label class="choice-option"><input type="radio" name="reminder_target" value="exact"><span class="choice-copy"><svg class="choice-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-clock"/></svg><span>Точное время</span></span></label>
              <label class="choice-option" id="keep-reminder-option" hidden><input type="radio" name="reminder_target" value="keep"><span id="keep-reminder-label">Текущий набор</span></label>
            </div>
            <label class="field" id="exact-times-field" hidden>
              <span class="field-label">Время приёма</span>
              <input name="times" type="text" inputmode="numeric" placeholder="08:00 или 08:00, 21:00">
              <span class="field-hint">Несколько значений разделяйте запятыми.</span>
            </label>
          </section>

          <section class="form-section" aria-labelledby="schedule-section-title">
            <h2 class="form-section-title" id="schedule-section-title">Периодичность</h2>
            <label class="field">
              <span class="field-label">Как часто</span>
              <select name="schedule_kind" id="create-schedule-kind">
                <option value="daily">Каждый день</option>
                <option value="interval">Каждые N дней</option>
                <option value="weekdays">По дням недели</option>
              </select>
            </label>
            <label class="field" id="interval-field" hidden>
              <span class="field-label">Интервал в днях</span>
              <input name="every_days" type="number" min="1" max="365" inputmode="numeric" placeholder="3">
            </label>
            <div class="field" id="weekdays-field" hidden>
              <span class="field-label">Дни недели</span>
              <div class="weekday-grid">
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="1"><span>Пн</span></label>
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="2"><span>Вт</span></label>
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="3"><span>Ср</span></label>
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="4"><span>Чт</span></label>
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="5"><span>Пт</span></label>
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="6"><span>Сб</span></label>
                <label class="weekday-option"><input type="checkbox" name="weekdays" value="7"><span>Вс</span></label>
              </div>
              <span class="field-hint">Выберите хотя бы один день.</span>
            </div>
          </section>

          <section class="form-section" aria-labelledby="course-section-title">
            <h2 class="form-section-title" id="course-section-title">Продолжительность курса</h2>
            <label class="field">
              <span class="field-label">Начать</span>
              <input name="start_date" id="create-start-date" type="date" required>
            </label>
            <label class="field">
              <span class="field-label">Завершить</span>
              <select name="ending_kind" id="create-ending-kind">
                <option value="unchanged" id="unchanged-ending-option" hidden>Не менять</option>
                <option value="total_intakes">После заданного числа приёмов</option>
                <option value="end_date">В выбранную дату</option>
                <option value="open_ended">Без даты окончания</option>
              </select>
            </label>
            <label class="field" id="total-intakes-field">
              <span class="field-label">Количество приёмов</span>
              <input name="total_intakes" type="number" min="1" max="10000" inputmode="numeric" placeholder="30" required>
            </label>
            <label class="field" id="end-date-field" hidden>
              <span class="field-label">Последний день курса</span>
              <input name="end_date" id="create-end-date" type="date">
            </label>
          </section>

          <p class="form-error" id="regimen-create-error" role="alert" tabindex="-1" hidden></p>
          <div class="form-actions">
            <button class="primary-button" id="save-regimen-button" type="submit">Сохранить курс</button>
          </div>
        </form>
      </section>

      <nav class="tabs" id="main-tabs" aria-label="Основные разделы">
        <span class="tab-indicator" id="tab-indicator" aria-hidden="true"></span>
        <button class="tab" id="today-tab" type="button" aria-current="page" aria-controls="today-panel">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-calendar-check"/></svg>
          <span>Сегодня</span>
        </button>
        <button class="tab" id="regimens-tab" type="button" aria-controls="regimens-panel">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-pill"/></svg>
          <span>Курсы</span>
        </button>
        <button class="tab" id="family-tab" type="button" aria-controls="family-panel">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-users"/></svg>
          <span>Семья</span>
        </button>
        <button class="tab" id="history-tab" type="button" aria-controls="history-panel">
          <svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-history"/></svg>
          <span>История</span>
        </button>
      </nav>
    </div>
  </main>

  <script>
    const tg = window.Telegram?.WebApp;
    tg?.ready();
    tg?.expand();

    const state = {
      dashboard: null, regimens: null, family: null, setsData: null, historyDays: 7, view: 'today',
      busyEventId: null, busySetId: null, busyRegimenId: null,
      busyCreate: false, busySettings: false, busySets: false, busyFamily: false, busyReport: false,
      editingRegimenId: null, editingSetKey: null, snoozeEventId: null,
      collapsedRegimenPeriods: new Set(), report: null
    };
    const pendingStatuses = new Set(['scheduled', 'due', 'snoozed']);
    const correctableStatuses = new Set(['skipped', 'missed']);
    const statusLabels = {
      scheduled: 'Запланировано', due: 'Пора', snoozed: 'Отложено', taken: 'Принято',
      skipped: 'Пропущено', missed: 'Не отмечено', cancelled: 'Отменено'
    };
    const regimenStatusLabels = { active: 'Активен', paused: 'На паузе', completed: 'Завершён' };
    const doseUnits = {
      tablet: ['таблетка'], capsule: ['капсула'], injection: ['мл', 'мг'],
      drops: ['капля', 'мл'], other: ['мг', 'мл']
    };

    const byId = (id) => document.getElementById(id);
    let initData = tg?.initData || '';
    let localSessionError = '';
    const detectedZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

    function setVisible(id, visible) { byId(id).hidden = !visible; }

    function setGlobalStatus(message, isError = false) {
      const element = byId('global-status');
      element.textContent = message;
      element.classList.toggle('error', isError);
    }

    function clearFormError(form, errorElement) {
      errorElement.hidden = true;
      errorElement.textContent = '';
      form.querySelectorAll('[aria-invalid="true"]').forEach((field) => {
        field.removeAttribute('aria-invalid');
        if (field.getAttribute('aria-describedby') === errorElement.id) {
          field.removeAttribute('aria-describedby');
        }
      });
    }

    function showFormError(form, errorElement, error, fieldName = error.fieldName) {
      errorElement.textContent = error.message;
      errorElement.hidden = false;
      const field = fieldName ? form.querySelector(`[name="${fieldName}"]`) : null;
      if (field) {
        field.setAttribute('aria-invalid', 'true');
        field.setAttribute('aria-describedby', errorElement.id);
      }
      window.requestAnimationFrame(() => (field || errorElement).focus());
    }

    function fieldError(message, fieldName) {
      const error = new Error(message);
      error.fieldName = fieldName;
      return error;
    }

    function showOnly(section) {
      setVisible('loading-state', section === 'loading');
      setVisible('error-state', section === 'error');
      setVisible('setup-state', section === 'setup');
      setVisible('app-content', section === 'app');
      setVisible('settings-button', section === 'app');
    }

    async function request(path, body) {
      const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        let detail = '';
        try { detail = (await response.json()).detail || ''; } catch (_) { /* no JSON body */ }
        const error = new Error(detail || 'Request failed');
        error.status = response.status;
        throw error;
      }
      return response.json();
    }

    function errorMessage(error) {
      if (localSessionError) return localSessionError;
      if (!initData || error.status === 401) return 'Откройте приложение заново через кнопку в боте.';
      if (error.status === 503) return 'Сервис временно недоступен. Попробуйте немного позже.';
      return 'Проверьте соединение и попробуйте ещё раз.';
    }

    async function bootstrap() {
      localSessionError = '';
      if (!initData && ['127.0.0.1', 'localhost', '::1'].includes(location.hostname)) {
        try {
          const response = await fetch('/mini-app/local-session');
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || 'Локальный вход недоступен');
          initData = result.init_data;
        } catch (error) {
          localSessionError = error.message;
        }
      }
      await loadDashboard();
    }

    function localDate(value, options) {
      return new Intl.DateTimeFormat('ru-RU', { timeZone: state.dashboard.timezone, ...options })
        .format(new Date(value));
    }

    function todayLabel() {
      return new Intl.DateTimeFormat('ru-RU', {
        timeZone: state.dashboard.timezone, weekday: 'long', day: 'numeric', month: 'long'
      }).format(new Date());
    }

    function createBadge(status) {
      const badge = document.createElement('span');
      badge.className = `status-badge ${status}`;
      badge.textContent = statusLabels[status] || regimenStatusLabels[status] || status;
      return badge;
    }

    const iconSymbol = {
      tablet: 'icon-tablet',
      capsule: 'icon-pill',
      injection: 'icon-syringe',
      drops: 'icon-drop',
      other: 'icon-other',
      early: 'icon-clock',
      morning: 'icon-sunrise',
      day: 'icon-sun',
      evening: 'icon-moon',
      exact: 'icon-clock'
    };

    function createIcon(name, className = 'schedule-icon') {
      const icon = document.createElement('span');
      icon.className = className;
      icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none"><use href="#${iconSymbol[name] || iconSymbol.other}"></use></svg>`;
      return icon;
    }

    function createFormIcon(form) { return createIcon(form, 'med-icon'); }

    function formatDose(amount, unit) {
      const number = Number(String(amount).replace(',', '.'));
      const forms = {
        'таблетка': ['таблетка', 'таблетки', 'таблеток'],
        'таблетки': ['таблетка', 'таблетки', 'таблеток'],
        'таблеток': ['таблетка', 'таблетки', 'таблеток'],
        'капсула': ['капсула', 'капсулы', 'капсул'],
        'капсулы': ['капсула', 'капсулы', 'капсул'],
        'капсул': ['капсула', 'капсулы', 'капсул'],
        'капля': ['капля', 'капли', 'капель'],
        'капли': ['капля', 'капли', 'капель'],
        'капель': ['капля', 'капли', 'капель']
      }[String(unit).trim().toLocaleLowerCase('ru-RU')];
      if (!forms || !Number.isInteger(number)) return `${amount} ${unit}`;
      const absolute = Math.abs(number);
      const word = absolute % 100 >= 11 && absolute % 100 <= 14
        ? forms[2]
        : absolute % 10 === 1
          ? forms[0]
          : absolute % 10 >= 2 && absolute % 10 <= 4
            ? forms[1]
            : forms[2];
      return `${amount} ${word}`;
    }

    function mealTimingLabel(value) {
      return {
        independent: '',
        before: 'до еды',
        during: 'во время еды',
        after: 'после еды'
      }[value] || '';
    }

    function doseWithMeal(item) {
      const meal = mealTimingLabel(item.meal_timing);
      return `${formatDose(item.dose_amount, item.dose_unit)}${meal ? ` · ${meal}` : ''}`;
    }

    function createEventRow(event, actionable, showTime = true) {
      const item = document.createElement('li');
      item.className = `event-row${showTime ? '' : ' grouped'}${event.status === 'taken' ? ' is-complete' : ''}`;

      const displayedAt = event.status === 'taken' && event.taken_at
        ? event.taken_at
        : event.scheduled_at;
      const time = document.createElement('time');
      time.className = 'event-time';
      time.dateTime = displayedAt;
      time.textContent = localDate(displayedAt, { hour: '2-digit', minute: '2-digit' });

      const main = document.createElement('div');
      main.className = 'event-main';
      const titleLine = document.createElement('div');
      titleLine.className = 'event-title-line';
      const name = document.createElement('span');
      name.className = 'event-name';
      const nameCopy = document.createElement('span');
      nameCopy.className = 'med-name-copy';
      nameCopy.textContent = event.medication_name;
      name.append(createFormIcon(event.medication_form), nameCopy);
      titleLine.append(name, createBadge(event.status));

      const dose = document.createElement('p');
      dose.className = 'event-dose';
      const plannedTime = localDate(event.scheduled_at, { hour: '2-digit', minute: '2-digit' });
      dose.textContent = event.status === 'taken' && event.taken_at
        ? `${doseWithMeal(event)} · по плану ${plannedTime}`
        : doseWithMeal(event);
      if (event.status === 'snoozed' && event.snoozed_until) {
        const postponedTime = localDate(event.snoozed_until, { hour: '2-digit', minute: '2-digit' });
        dose.textContent = `${doseWithMeal(event)} · перенесено на ${postponedTime} · по плану ${plannedTime}`;
      }
      main.append(titleLine, dose);

      if (actionable && (pendingStatuses.has(event.status) || correctableStatuses.has(event.status))) {
        const actions = document.createElement('div');
        actions.className = 'event-actions';
        if (correctableStatuses.has(event.status)) actions.classList.add('corrective');
        const take = document.createElement('button');
        take.type = 'button';
        take.className = 'action-button take';
        take.textContent = 'Принять';
        take.setAttribute('aria-label', `${take.textContent}: ${event.medication_name}`);
        take.disabled = state.busyEventId === event.id || state.busySetId !== null;
        take.addEventListener('click', () => applyAction(event, 'take'));

        actions.append(take);

        if (pendingStatuses.has(event.status)) {
          if (event.status === 'due' || event.status === 'snoozed') {
            const snooze = document.createElement('button');
            snooze.type = 'button';
            snooze.className = 'action-button snooze';
            snooze.textContent = 'Отложить';
            snooze.setAttribute('aria-label', `Отложить: ${event.medication_name}`);
            snooze.disabled = state.busyEventId === event.id || state.busySetId !== null;
            snooze.addEventListener('click', () => {
              state.snoozeEventId = state.snoozeEventId === event.id ? null : event.id;
              renderToday();
            });
            actions.append(snooze);
          }
          const skip = document.createElement('button');
          skip.type = 'button';
          skip.className = 'action-button skip';
          skip.textContent = 'Пропустить';
          skip.setAttribute('aria-label', `Пропустить: ${event.medication_name}`);
          skip.disabled = state.busyEventId === event.id || state.busySetId !== null;
          skip.addEventListener('click', () => applyAction(event, 'skip'));
          actions.append(skip);
        }
        main.append(actions);

        if (state.snoozeEventId === event.id) {
          const choices = document.createElement('div');
          choices.className = 'snooze-options';
          [15, 30, 60].forEach((minutes) => {
            const choice = document.createElement('button');
            choice.type = 'button';
            choice.className = 'snooze-option';
            choice.textContent = `${minutes} мин`;
            choice.disabled = state.busyEventId === event.id;
            choice.addEventListener('click', () => applyAction(event, 'snooze', minutes));
            choices.append(choice);
          });
          main.append(choices);
        }
      }

      if (showTime) item.append(time, main); else item.append(main);
      return item;
    }

    function localMinutesNow() {
      const parts = new Intl.DateTimeFormat('ru-RU', {
        timeZone: state.dashboard.timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
      }).formatToParts(new Date());
      const hour = Number(parts.find((part) => part.type === 'hour')?.value || 0);
      const minute = Number(parts.find((part) => part.type === 'minute')?.value || 0);
      return hour * 60 + minute;
    }

    function timeMinutes(value) {
      const [hour, minute] = value.split(':').map(Number);
      return hour * 60 + minute;
    }

    function isCurrentGroup(medicationSet, events) {
      if (medicationSet.id === 'exact') {
        return events.some((event) => event.status === 'due' || event.status === 'snoozed');
      }
      if (!events.some((event) => pendingStatuses.has(event.status))) {
        return false;
      }
      const now = localMinutesNow();
      const start = timeMinutes(medicationSet.window_start);
      const end = timeMinutes(medicationSet.window_end);
      return start <= end ? now >= start && now <= end : now >= start || now <= end;
    }

    function setHeading(medicationSet, events, current) {
      const head = document.createElement('div');
      head.className = 'set-head';
      const text = document.createElement('div');
      const title = document.createElement('h2');
      title.className = 'set-title';
      const scheduleIcon = medicationSet.id === 'exact'
        ? 'exact'
        : ({ 'утро': 'morning', 'день': 'day', 'вечер': 'evening' }[
            medicationSet.name.toLocaleLowerCase('ru-RU')
          ] || 'tablet');
      title.append(createIcon(scheduleIcon), document.createTextNode(medicationSet.name));
      if (current) {
        const currentLabel = document.createElement('span');
        currentLabel.className = 'current-label';
        currentLabel.textContent = 'Сейчас';
        title.append(currentLabel);
      }
      const windowLabel = document.createElement('p');
      windowLabel.className = 'set-window';
      windowLabel.textContent = medicationSet.id === 'exact'
        ? 'Отдельные напоминания'
        : `${medicationSet.window_start}–${medicationSet.window_end}`;
      text.append(title, windowLabel);
      head.append(text);

      if (current
          && medicationSet.id !== 'exact'
          && events.some((event) => pendingStatuses.has(event.status))) {
        const takeAll = document.createElement('button');
        takeAll.type = 'button';
        takeAll.className = 'set-take-button';
        takeAll.textContent = state.busySetId === medicationSet.id ? 'Сохраняю…' : 'Принять всё';
        takeAll.setAttribute('aria-label', `Принять все препараты набора «${medicationSet.name}»`);
        takeAll.disabled = state.busySetId !== null || state.busyEventId !== null;
        takeAll.addEventListener('click', () => applySetAction(medicationSet));
        head.append(takeAll);
      }

      return head;
    }

    function createEventGroup(medicationSet, events) {
      const group = document.createElement('li');
      const current = isCurrentGroup(medicationSet, events);
      group.className = `set-group${current ? ' current' : ''}`;
      if (current) group.setAttribute('aria-current', 'true');
      const eventList = document.createElement('ul');
      eventList.className = 'set-events';
      events.forEach((event) => eventList.append(createEventRow(event, true, false)));
      group.append(setHeading(medicationSet, events, current), eventList);
      return group;
    }

    function renderToday() {
      const list = byId('today-list');
      list.replaceChildren();
      const currentIds = new Set(state.dashboard.current_event_ids);
      const events = state.dashboard.today.filter((event) => currentIds.has(event.id)).sort(
        (left, right) => new Date(left.scheduled_at) - new Date(right.scheduled_at)
      );
      const groupedEventIds = new Set();
      const groupOrder = { 'утро': 0, 'день': 1, 'вечер': 2 };
      const medicationSets = [...(state.dashboard.today_sets || [])].sort((left, right) => (
        (groupOrder[left.name.toLocaleLowerCase('ru-RU')] ?? 3)
        - (groupOrder[right.name.toLocaleLowerCase('ru-RU')] ?? 3)
      ));
      medicationSets.forEach((medicationSet) => {
        const eventIds = new Set(medicationSet.event_ids);
        const setEvents = events.filter((event) => eventIds.has(event.id));
        setEvents.forEach((event) => groupedEventIds.add(event.id));
        if (setEvents.length) list.append(createEventGroup(medicationSet, setEvents));
      });
      const exactEvents = events.filter((event) => !groupedEventIds.has(event.id));
      if (exactEvents.length) {
        list.append(createEventGroup({
          id: 'exact', name: 'По времени', window_start: 'точное', window_end: 'время'
        }, exactEvents));
      }
      byId('today-date').textContent = todayLabel();
      byId('edit-intakes-button').hidden = state.dashboard.today.every((event) => event.status === 'cancelled');
    }

    function renderIntakeEditor() {
      const list = byId('intake-editor-list');
      list.replaceChildren();
      const events = [...state.dashboard.today]
        .filter((event) => event.status !== 'cancelled')
        .sort((left, right) => new Date(left.scheduled_at) - new Date(right.scheduled_at));
      events.forEach((event) => {
        const row = createEventRow(event, false);
        const taken = event.status === 'taken';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'regimen-button';
        button.textContent = taken ? 'Принято · отменить' : 'Не принято · принять';
        button.setAttribute('aria-pressed', String(taken));
        button.setAttribute('aria-label', `${button.textContent}: ${event.medication_name}`);
        button.disabled = state.busyEventId !== null || state.busySetId !== null;
        button.addEventListener('click', () => applyAction(event, taken ? 'undo' : 'take', null, true));
        row.querySelector('.event-main').append(button);
        list.append(row);
      });
    }

    async function applySetAction(medicationSet) {
      if (state.busySetId || state.busyEventId) return;
      state.busySetId = medicationSet.id;
      setGlobalStatus(`Отмечаем набор «${medicationSet.name}»…`);
      renderSummary();
      renderToday();
      try {
        const result = await request(`/mini-app/sets/${encodeURIComponent(medicationSet.id)}/take`, {
          init_data: initData
        });
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus(`Набор отмечен · ${result.updated_count} приёмов`);
        await loadDashboard({ silent: true });
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(error.status === 409
          ? 'Набор уже отмечен. Обновляем данные…'
          : errorMessage(error), true);
        await loadDashboard({ silent: true });
      } finally {
        state.busySetId = null;
        if (state.dashboard) {
          renderSummary();
          renderToday();
        }
      }
    }

    function historyDateKey(event) {
      const occurredAt = event.status === 'taken' && event.taken_at
        ? event.taken_at
        : event.scheduled_at;
      return localDate(occurredAt, { year: 'numeric', month: '2-digit', day: '2-digit' });
    }

    function renderHistory() {
      const container = byId('history-list');
      container.replaceChildren();
      const events = state.dashboard.history.filter((event) => event.status !== 'cancelled');
      const hasPlanned = events.some((event) => pendingStatuses.has(event.status));
      setVisible('history-planned-note', hasPlanned);
      let currentDate = '';
      let currentList = null;
      events.forEach((event) => {
        const key = historyDateKey(event);
        if (key !== currentDate) {
          currentDate = key;
          const heading = document.createElement('h3');
          heading.className = 'date-heading';
          const occurredAt = event.status === 'taken' && event.taken_at
            ? event.taken_at
            : event.scheduled_at;
          heading.textContent = localDate(occurredAt, {
            weekday: 'long', day: 'numeric', month: 'long'
          });
          currentList = document.createElement('ul');
          currentList.className = 'event-list';
          container.append(heading, currentList);
        }
        currentList.append(createEventRow(event, true));
      });
      setVisible('history-empty', events.length === 0);
    }

    function renderSummary() {
      const upcomingIntake = state.dashboard.next_intake;
      byId('next-scheduled-intake').textContent = '';
      const events = state.dashboard.today.filter((event) => event.status !== 'cancelled');
      const taken = events.filter((event) => event.status === 'taken').length;
      const total = events.length;
      const percent = total === 0 ? 0 : Math.round(taken / total * 100);
      byId('daily-progress').textContent = `${taken} из ${total}`;
      byId('daily-progress-percent').textContent = `${percent}%`;
      byId('daily-progress-bar').style.width = `${percent}%`;
      const progress = byId('daily-progress-track');
      progress.setAttribute('aria-valuemax', String(total));
      progress.setAttribute('aria-valuenow', String(taken));

      const next = byId('next-intake');
      const nextLabel = byId('next-intake-label');
      const nextDetail = byId('next-intake-detail');
      const nextAction = byId('next-intake-action');
      const currentIds = new Set(state.dashboard.current_event_ids);
      const currentEvents = events.filter((event) => currentIds.has(event.id));
      const urgent = currentEvents.find((event) => event.status === 'due' || event.status === 'snoozed');
      const upcoming = currentEvents
        .filter((event) => event.status === 'scheduled')
        .sort((left, right) => new Date(left.scheduled_at) - new Date(right.scheduled_at))[0];
      const active = urgent || upcoming;
      nextAction.hidden = true;
      nextAction.onclick = null;
      if (active) {
        const activeSet = (state.dashboard.today_sets || []).find((medicationSet) => {
          const setEvents = currentEvents.filter((event) => medicationSet.event_ids.includes(event.id));
          return medicationSet.id !== 'exact'
            && medicationSet.event_ids.includes(active.id)
            && isCurrentGroup(medicationSet, setEvents);
        });
        nextLabel.textContent = 'Сейчас';
        if (activeSet) {
          const setEvents = currentEvents.filter((event) => activeSet.event_ids.includes(event.id));
          const pendingSetEvents = setEvents.filter((event) => pendingStatuses.has(event.status));
          const medications = [...new Set(pendingSetEvents.map((event) => event.medication_name))];
          next.textContent = medications.join(', ');
          nextDetail.textContent = `${activeSet.name} · ${activeSet.window_start}–${activeSet.window_end}`;
          nextAction.textContent = state.busySetId === activeSet.id ? 'Сохраняю…' : 'Принять всё';
          nextAction.setAttribute('aria-label', `Принять все препараты набора «${activeSet.name}»`);
          nextAction.disabled = state.busySetId !== null || state.busyEventId !== null;
          nextAction.onclick = () => applySetAction(activeSet);
          nextAction.hidden = false;
        } else {
          next.textContent = active.medication_name;
          const time = localDate(active.scheduled_at, { hour: '2-digit', minute: '2-digit' });
          nextDetail.textContent = `${time} · ${doseWithMeal(active)}`;
          if (pendingStatuses.has(active.status)) {
            const actionLabel = 'Принять';
            nextAction.textContent = state.busyEventId === active.id ? 'Сохраняю…' : actionLabel;
            nextAction.setAttribute('aria-label', `${actionLabel}: ${active.medication_name}`);
            nextAction.disabled = state.busyEventId !== null || state.busySetId !== null;
            nextAction.onclick = () => applyAction(active, 'take');
            nextAction.hidden = false;
          }
        }
      } else if (upcomingIntake) {
        nextLabel.textContent = 'Следующий приём';
        next.textContent = upcomingIntake.label;
        nextDetail.textContent = `${localDate(upcomingIntake.at, { hour: '2-digit', minute: '2-digit' })} · Напомним по расписанию.`;
      } else if (total === 0) {
        nextLabel.textContent = 'Сегодня';
        next.textContent = 'Приёмов нет';
        nextDetail.textContent = 'Новых действий не требуется.';
      } else if (taken === total) {
        nextLabel.textContent = 'Сегодня';
        next.textContent = 'На сегодня всё';
        nextDetail.textContent = 'Все приёмы отмечены.';
      } else {
        nextLabel.textContent = 'Сегодня';
        next.textContent = 'Сейчас действий нет';
        nextDetail.textContent = 'При необходимости отметьте приём вручную.';
      }

      const summary = state.dashboard.summary;
      const history = byId('history-summary');
      const period = state.historyDays === 30 ? '30 дней' : '7 дней';
      if (summary.adherence_percent === null) {
        history.textContent = `За ${period} ещё нет отмеченных приёмов.`;
      } else {
        history.innerHTML = `За ${period}: <strong>${summary.adherence_percent}% соблюдения</strong> · принято ${summary.taken} · пропущено ${summary.skipped}`;
      }
    }

    function regimenProperty(list, label, value) {
      const term = document.createElement('dt');
      term.textContent = label;
      const description = document.createElement('dd');
      description.textContent = value;
      list.append(term, description);
    }

    function regimenActionButton(regimen, label, action, danger = false) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `regimen-button${danger ? ' danger' : ''}`;
      button.textContent = label;
      button.disabled = state.busyRegimenId === regimen.id;
      button.addEventListener('click', () => applyRegimenAction(regimen, action));
      return button;
    }

    function regimenEditButton(regimen) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'regimen-button';
      button.textContent = 'Изменить';
      button.disabled = state.busyRegimenId === regimen.id;
      button.addEventListener('click', () => openEditRegimen(regimen));
      return button;
    }

    function regimenDeleteButton(regimen) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'regimen-button danger';
      button.textContent = 'Удалить';
      button.disabled = state.busyRegimenId === regimen.id;
      button.addEventListener('click', () => deleteRegimen(regimen));
      return button;
    }

    function nextIntakeProperty(regimen) {
      if (regimen.status === 'paused') return ['Статус', 'Курс приостановлен'];
      if (regimen.status === 'completed') return ['Статус', 'Курс завершён'];
      if (!regimen.next_intake_at) return ['Статус', 'Нет запланированных приёмов'];
      const formatted = localDate(regimen.next_intake_at, {
        weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
      });
      return new Date(regimen.next_intake_at) < new Date()
        ? ['Просрочен', formatted] : ['Следующий', formatted];
    }

    const regimenPeriodGroups = [
      { key: 'early', label: 'Раннее время', time: '00:00–05:59' },
      { key: 'morning', label: 'Утро', time: '06:00–10:59' },
      { key: 'day', label: 'День', time: '11:00–17:59' },
      { key: 'evening', label: 'Вечер', time: '18:00–23:59' }
    ];

    function regimenListItem(regimen) {
      const item = document.createElement('li');
      item.className = 'regimen-row';
      const head = document.createElement('div');
      head.className = 'regimen-head';
      const title = document.createElement('span');
      title.className = 'regimen-title';
      title.append(
        createFormIcon(regimen.medication_form),
        document.createTextNode(regimen.medication_name)
      );
      head.append(title, createBadge(regimen.status));

      const properties = document.createElement('dl');
      properties.className = 'regimen-properties';
      regimenProperty(properties, 'Доза', doseWithMeal(regimen));
      regimenProperty(properties, ...nextIntakeProperty(regimen));
      regimenProperty(properties, 'График', regimen.schedule);
      const startDate = new Intl.DateTimeFormat('ru-RU').format(
        new Date(`${regimen.start_date}T12:00:00`)
      );
      regimenProperty(properties, 'Курс', `${regimen.ending} · с ${startDate}`);
      item.append(head, properties);

      if (state.dashboard.can_manage_personal_regimens) {
        const actions = document.createElement('div');
        actions.className = 'regimen-actions';
        const more = document.createElement('details');
        more.className = 'regimen-more';
        const moreLabel = document.createElement('summary');
        moreLabel.textContent = 'Ещё';
        moreLabel.setAttribute('aria-label', `Другие действия: ${regimen.medication_name}`);
        const moreMenu = document.createElement('div');
        moreMenu.className = 'regimen-more-menu';
        if (regimen.status !== 'completed') {
          if (regimen.status === 'active') {
            actions.append(regimenEditButton(regimen));
            moreMenu.append(regimenActionButton(regimen, 'Приостановить', 'pause'));
          } else {
            actions.append(regimenActionButton(regimen, 'Возобновить', 'resume'));
          }
          moreMenu.append(regimenActionButton(regimen, 'Завершить курс', 'complete', true));
        }
        moreMenu.append(regimenDeleteButton(regimen));
        more.append(moreLabel, moreMenu);
        actions.append(more);
        item.append(actions);
      }
      return item;
    }

    function renderRegimens() {
      const list = byId('regimen-list');
      const jumpNav = byId('regimen-jump-nav');
      list.replaceChildren();
      jumpNav.replaceChildren();
      const regimens = state.regimens || [];
      const groups = regimenPeriodGroups.map((period) => ({
        ...period,
        regimens: regimens.filter((regimen) => regimen.intake_periods?.includes(period.key))
      })).filter((group) => group.regimens.length);
      groups.forEach((group) => {
        const section = document.createElement('li');
        section.className = 'regimen-group';
        section.id = `regimen-group-${group.key}`;
        const details = document.createElement('details');
        details.className = 'regimen-group-details';
        details.open = !state.collapsedRegimenPeriods.has(group.key);
        const head = document.createElement('summary');
        head.className = 'regimen-group-head';
        const heading = document.createElement('span');
        heading.className = 'regimen-group-title';
        heading.textContent = group.label;
        const time = document.createElement('span');
        time.className = 'regimen-group-time';
        time.textContent = group.time;
        const count = document.createElement('span');
        count.className = 'regimen-group-count';
        count.textContent = String(group.regimens.length);
        head.append(createIcon(group.key), heading, time, count);
        const groupList = document.createElement('ul');
        groupList.className = 'regimen-group-list';
        groupList.append(...group.regimens.map(regimenListItem));
        details.append(head, groupList);
        details.addEventListener('toggle', () => {
          if (details.open) state.collapsedRegimenPeriods.delete(group.key);
          else state.collapsedRegimenPeriods.add(group.key);
        });
        section.append(details);
        list.append(section);

        const jumpButton = document.createElement('button');
        jumpButton.type = 'button';
        jumpButton.className = 'regimen-jump-button';
        jumpButton.textContent = `${group.label} · ${group.regimens.length}`;
        jumpButton.addEventListener('click', () => {
          state.collapsedRegimenPeriods.delete(group.key);
          details.open = true;
          section.scrollIntoView({ block: 'start' });
        });
        jumpNav.append(jumpButton);
      });
      setVisible('regimen-jump-nav', groups.length > 1);
      setVisible('regimens-loading', false);
      setVisible('regimens-empty', regimens.length === 0);
    }

    async function loadRegimens(options = {}) {
      if (!options.silent) setVisible('regimens-loading', true);
      try {
        const response = await request('/mini-app/regimens', { init_data: initData });
        state.regimens = response.regimens;
        renderRegimens();
      } catch (error) {
        setVisible('regimens-loading', false);
        setGlobalStatus(errorMessage(error), true);
      }
    }

    function reportRequestBody() {
      return {
        init_data: initData,
        period: byId('report-period').value,
        regimen_id: byId('report-regimen').value || null
      };
    }

    function reportMetric(label, value) {
      const item = document.createElement('div');
      item.className = 'report-metric';
      const name = document.createElement('span');
      name.textContent = label;
      const result = document.createElement('strong');
      result.textContent = value;
      item.append(name, result);
      return item;
    }

    function displayIsoDate(value) {
      const [year, month, day] = value.split('-');
      return `${day}.${month}.${year}`;
    }

    function renderReport(report) {
      const metrics = byId('report-metrics');
      metrics.replaceChildren(
        reportMetric('Принято', String(report.summary.taken)),
        reportMetric('Пропущено', String(report.summary.skipped)),
        reportMetric('Ожидает', String(report.summary.pending)),
        reportMetric('Соблюдение', report.summary.adherence_percent === null
          ? '—' : `${report.summary.adherence_percent}%`)
      );
      const courses = byId('report-course-list');
      courses.replaceChildren();
      report.courses.forEach((course) => {
        const item = document.createElement('li');
        item.className = 'report-course';
        const name = document.createElement('strong');
        name.textContent = course.medication_name;
        const details = document.createElement('p');
        const progress = course.total_intakes === null
          ? `принято ${course.taken}`
          : `выполнено ${course.taken} из ${course.total_intakes} · осталось ${course.remaining_to_target}`;
        details.textContent = `${formatDose(course.dose_amount, course.dose_unit)} · с ${displayIsoDate(course.start_date)} · ${progress}`;
        const status = document.createElement('p');
        status.textContent = `Пропущено ${course.missed} · ожидает ${course.pending}`;
        item.append(name, details, status);
        courses.append(item);
      });
      const note = byId('report-note');
      note.textContent = 'В PDF — итоги за период и прогресс курсов. Подробная история доступна в приложении.';
      setVisible('report-preview', true);
      setVisible('report-download', true);
    }

    async function openReport() {
      if (state.regimens === null) await loadRegimens({ silent: true });
      const select = byId('report-regimen');
      select.replaceChildren(new Option('Все препараты', ''));
      (state.regimens || []).forEach((regimen) => {
        select.append(new Option(regimen.medication_name, regimen.id));
      });
      state.report = null;
      setVisible('report-preview', false);
      setVisible('report-download', false);
      clearFormError(byId('report-form'), byId('report-error'));
      byId('report-dialog').showModal();
    }

    async function generateReport(event) {
      event.preventDefault();
      if (state.busyReport) return;
      const form = event.currentTarget;
      state.busyReport = true;
      const button = byId('report-generate');
      const errorElement = byId('report-error');
      clearFormError(form, errorElement);
      button.disabled = true;
      button.textContent = 'Считаю…';
      try {
        state.report = await request('/mini-app/reports/preview', reportRequestBody());
        renderReport(state.report);
      } catch (error) {
        showFormError(form, errorElement, new Error(
          error.status === 404 ? 'Курс не найден.' : errorMessage(error)
        ));
      } finally {
        state.busyReport = false;
        button.disabled = false;
        button.textContent = 'Показать';
      }
    }

    async function downloadReport() {
      if (state.busyReport) return;
      state.busyReport = true;
      const button = byId('report-download');
      button.disabled = true;
      button.textContent = 'Готовлю PDF…';
      byId('report-error').hidden = true;
      try {
        const result = await request('/mini-app/reports/pdf-link', reportRequestBody());
        const url = new URL(result.url, location.href).href;
        if (tg?.openLink && location.protocol === 'https:') {
          tg.openLink(url);
        } else {
          const link = document.createElement('a');
          link.href = url;
          link.target = '_blank';
          link.rel = 'noopener';
          document.body.append(link);
          link.click();
          link.remove();
        }
        setGlobalStatus('PDF подготовлен');
      } catch (error) {
        const errorElement = byId('report-error');
        errorElement.textContent = errorMessage(error);
        errorElement.hidden = false;
      } finally {
        state.busyReport = false;
        button.disabled = false;
        button.textContent = 'Скачать PDF';
      }
    }

    function familyRow(titleContent, meta, trailing = null, tagName = 'li') {
      const row = document.createElement(tagName);
      row.className = 'family-row';
      const main = document.createElement('div');
      main.className = 'family-row-main';
      const title = document.createElement('div');
      title.className = 'family-row-title';
      if (typeof titleContent === 'string') title.textContent = titleContent;
      else title.append(titleContent);
      const details = document.createElement('p');
      details.className = 'family-row-meta';
      details.textContent = meta;
      main.append(title, details);
      row.append(main);
      if (trailing) {
        row.append(trailing);
        if (trailing.classList?.contains('family-actions')) row.classList.add('has-actions');
      }
      return row;
    }

    function familyAction(label, handler, danger = false) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `family-action${danger ? ' danger' : ''}`;
      button.textContent = label;
      button.disabled = state.busyFamily;
      button.addEventListener('click', handler);
      return button;
    }

    function askFamilyName(title, label, value = '') {
      const dialog = byId('family-dialog');
      if (!dialog.showModal) {
        const result = window.prompt(`${title}\n${label}`, value);
        return Promise.resolve(result?.trim() || null);
      }
      byId('family-dialog-title').textContent = title;
      byId('family-dialog-label').textContent = label;
      const input = byId('family-dialog-input');
      input.value = value;
      dialog.returnValue = '';
      dialog.showModal();
      requestAnimationFrame(() => input.focus());
      return new Promise((resolve) => {
        dialog.addEventListener('close', () => {
          const result = dialog.returnValue === 'save' ? input.value.trim() : '';
          resolve(result || null);
        }, { once: true });
      });
    }

    function confirmFamilyDelete(message) {
      if (tg?.showConfirm) return new Promise((resolve) => tg.showConfirm(message, resolve));
      return Promise.resolve(window.confirm(message));
    }

    function askFamilyInvitation(preselectedGroupId = '') {
      const groups = state.family?.groups || [];
      const dialog = byId('family-invite-dialog');
      if (!dialog.showModal) {
        const group = groups.find((item) => item.id === preselectedGroupId) || groups[0];
        const groupName = group ? '' : window.prompt('Название новой группы', '');
        const displayName = window.prompt('Как называть участника', '');
        if ((!group && !groupName?.trim()) || !displayName?.trim()) return Promise.resolve(null);
        const selfManaged = window.confirm(
          'Разрешить участнику добавлять собственные курсы?'
        );
        return Promise.resolve({
          group_id: group?.id || null,
          group_name: group ? null : groupName.trim(),
          group_label: group?.name || groupName.trim(),
          display_name: displayName.trim(),
          role: selfManaged ? 'self_managed' : 'dependent'
        });
      }
      const select = byId('family-invite-group');
      select.replaceChildren();
      groups.forEach((group) => select.add(new Option(group.name, group.id)));
      select.add(new Option('Новая группа', 'new'));
      select.value = preselectedGroupId || (groups[0]?.id || 'new');
      const newGroupField = byId('family-new-group-field');
      const newGroupInput = byId('family-new-group-name');
      const syncGroup = () => {
        const isNew = select.value === 'new';
        newGroupField.hidden = !isNew;
        newGroupInput.required = isNew;
      };
      syncGroup();
      select.onchange = syncGroup;
      newGroupInput.value = '';
      byId('family-invite-name').value = '';
      dialog.returnValue = '';
      dialog.showModal();
      return new Promise((resolve) => {
        dialog.addEventListener('close', () => {
          if (dialog.returnValue !== 'save') {
            resolve(null);
            return;
          }
          const selected = groups.find((group) => group.id === select.value);
          const groupName = newGroupInput.value.trim();
          const displayName = byId('family-invite-name').value.trim();
          const role = new FormData(byId('family-invite-form')).get('family_role');
          if ((!selected && !groupName) || !displayName) {
            resolve(null);
            return;
          }
          resolve({
            group_id: selected?.id || null,
            group_name: selected ? null : groupName,
            group_label: selected?.name || groupName,
            display_name: displayName,
            role
          });
        }, { once: true });
      });
    }

    async function runFamilyMutation(path, body, successMessage) {
      if (state.busyFamily) return false;
      state.busyFamily = true;
      renderFamily();
      setGlobalStatus('Сохраняем изменения…');
      try {
        await request(path, { init_data: initData, ...body });
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus(successMessage);
        return true;
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(error.status < 500 ? error.message : errorMessage(error), true);
        return false;
      } finally {
        state.busyFamily = false;
        await loadFamily({ silent: true });
      }
    }

    async function inviteFamilyMember(groupId = '') {
      if (state.busyFamily) return;
      const details = await askFamilyInvitation(groupId);
      if (!details) return;
      state.busyFamily = true;
      renderFamily();
      setGlobalStatus('Создаём приглашение…');
      try {
        const invitation = await request('/mini-app/family/invitations', {
          init_data: initData,
          group_id: details.group_id,
          group_name: details.group_name,
          display_name: details.display_name,
          role: details.role
        });
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus('Приглашение создано');
        const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(invitation.url)}&text=${encodeURIComponent(`Присоединяйтесь к группе «${details.group_label}» в Вовремя`)}`;
        if (tg?.openTelegramLink) tg.openTelegramLink(shareUrl);
        else if (navigator.share) await navigator.share({ title: 'Вовремя', url: invitation.url });
        else {
          await navigator.clipboard.writeText(invitation.url);
          setGlobalStatus('Ссылка приглашения скопирована');
        }
      } catch (error) {
        if (error?.name !== 'AbortError') {
          tg?.HapticFeedback?.notificationOccurred('error');
          setGlobalStatus(error.status < 500 ? error.message : errorMessage(error), true);
        }
      } finally {
        state.busyFamily = false;
        await loadFamily({ silent: true });
      }
    }

    async function renameFamilyGroup(group) {
      const name = await askFamilyName('Название группы', 'Новое название', group.name);
      if (!name || name === group.name) return;
      await runFamilyMutation(
        `/mini-app/family/groups/${encodeURIComponent(group.id)}/rename`,
        { name }, 'Группа переименована'
      );
    }

    async function deleteFamilyGroup(group) {
      const confirmed = await confirmFamilyDelete(
        `Удалить группу «${group.name}»? Все созданные в ней курсы и уведомления прекратятся. Это действие нельзя отменить.`
      );
      if (!confirmed) return;
      await runFamilyMutation(
        `/mini-app/family/groups/${encodeURIComponent(group.id)}/delete`,
        {}, 'Группа и семейные курсы удалены'
      );
    }

    async function renameFamilyMember(member) {
      const name = await askFamilyName('Имя участника', 'Новое имя', member.display_name);
      if (!name || name === member.display_name) return;
      await runFamilyMutation(
        `/mini-app/family/members/${encodeURIComponent(member.id)}/rename`,
        { name }, 'Имя участника изменено'
      );
    }

    async function deleteFamilyMember(member) {
      const confirmed = await confirmFamilyDelete(
        `Удалить участника «${member.display_name}»? Его семейные курсы и уведомления прекратятся. Это действие нельзя отменить.`
      );
      if (!confirmed) return;
      await runFamilyMutation(
        `/mini-app/family/members/${encodeURIComponent(member.id)}/delete`,
        {}, 'Участник и его семейные курсы удалены'
      );
    }

    function renderFamily() {
      const family = state.family || { groups: [], today: [], assignments: [] };
      const hasGroups = family.groups.length > 0;
      setVisible('family-loading', false);
      setVisible('family-empty', !hasGroups);
      setVisible('family-content', hasGroups);
      setVisible('family-actions', hasGroups);
      if (!hasGroups) return;

      const groupsList = byId('family-groups-list');
      groupsList.replaceChildren();
      family.groups.forEach((group) => {
        const groupItem = document.createElement('li');
        groupItem.className = 'family-group';
        const groupActions = document.createElement('div');
        groupActions.className = 'family-actions';
        groupActions.append(
          familyAction('Добавить', () => inviteFamilyMember(group.id)),
          familyAction('Изменить', () => renameFamilyGroup(group)),
          familyAction('Удалить', () => deleteFamilyGroup(group), true)
        );
        groupItem.append(familyRow(
          group.name,
          group.members.length ? `${group.members.length} участник(а)` : 'Участников пока нет',
          groupActions,
          'div'
        ));
        const membersList = document.createElement('ul');
        membersList.className = 'family-members';
        group.members.forEach((member) => {
          const memberActions = document.createElement('div');
          memberActions.className = 'family-actions';
          memberActions.append(
            familyAction('Изменить', () => renameFamilyMember(member)),
            familyAction('Удалить', () => deleteFamilyMember(member), true)
          );
          const roleLabel = member.role === 'dependent'
            ? 'Только отмечает приёмы'
            : 'Может добавлять свои приёмы';
          membersList.append(familyRow(member.display_name, roleLabel, memberActions));
        });
        groupItem.append(membersList);
        groupsList.append(groupItem);
      });

      const todayList = byId('family-today-list');
      todayList.replaceChildren();
      const taken = family.today.filter((item) => item.status === 'taken').length;
      byId('family-today-summary').textContent = family.today.length
        ? `Выполнено ${taken} из ${family.today.length}`
        : 'На сегодня приёмов нет.';
      family.today.forEach((item) => {
        const title = document.createElement('span');
        title.textContent = `${item.display_name} · ${item.medication_name}`;
        const time = document.createElement('time');
        time.className = 'family-status-time';
        time.dateTime = item.resolved_at || item.scheduled_at;
        const shownAt = item.resolved_at || item.scheduled_at;
        time.textContent = new Intl.DateTimeFormat('ru-RU', {
          timeZone: item.timezone, hour: '2-digit', minute: '2-digit'
        }).format(new Date(shownAt));
        const status = statusLabels[item.status] || item.status;
        todayList.append(familyRow(
          title,
          `${formatDose(item.dose_amount, item.dose_unit)} · ${item.group_name} · ${status}`,
          time
        ));
      });

      const assignmentsList = byId('family-assignments-list');
      assignmentsList.replaceChildren();
      family.assignments.forEach((assignment) => {
        const title = document.createElement('span');
        title.append(
          createFormIcon(assignment.medication_form),
          document.createTextNode(assignment.medication_name)
        );
        assignmentsList.append(familyRow(
          title,
          `${assignment.display_name} · ${assignment.group_name} · ${regimenStatusLabels[assignment.status] || assignment.status}`
        ));
      });
      setVisible('family-today-section', true);
      setVisible('family-assignments-section', family.assignments.length > 0);
    }

    async function loadFamily(options = {}) {
      if (state.busyFamily) return;
      state.busyFamily = true;
      if (!options.silent) setVisible('family-loading', true);
      byId('refresh-family-button').disabled = true;
      try {
        state.family = await request('/mini-app/family', { init_data: initData });
        state.busyFamily = false;
        renderFamily();
        if (options.silent) setGlobalStatus('Семейные статусы обновлены');
      } catch (error) {
        setVisible('family-loading', false);
        setGlobalStatus(errorMessage(error), true);
      } finally {
        state.busyFamily = false;
        byId('refresh-family-button').disabled = false;
      }
    }

    const setPresets = {
      morning: { name: 'Утро', icon: 'morning', window: '06:00–12:00' },
      day: { name: 'День', icon: 'day', window: '11:00–17:00' },
      evening: { name: 'Вечер', icon: 'evening', window: '18:00–23:00' }
    };

    function setIconName(name) {
      const normalized = name.toLocaleLowerCase('ru-RU');
      return Object.values(setPresets).find(
        (preset) => preset.name.toLocaleLowerCase('ru-RU') === normalized
      )?.icon || 'tablet';
    }

    function setCandidates(setId = null) {
      return (state.setsData?.regimens || []).filter((regimen) => (
        regimen.assigned_set_id === setId
        || (regimen.assigned_set_id === null && regimen.status === 'active')
      ));
    }

    function renderSetEditor(container, key, currentIds = []) {
      const setId = key.startsWith('new:') ? null : key;
      const editor = document.createElement('div');
      editor.className = 'set-editor';
      editor.dataset.setEditor = key;
      const title = document.createElement('span');
      title.className = 'setting-title';
      title.textContent = setId ? 'Состав набора' : 'Выберите препараты';
      editor.append(title);

      const candidates = setCandidates(setId);
      if (candidates.length === 0) {
        const note = document.createElement('p');
        note.className = 'setting-description';
        note.textContent = 'Нет свободных активных курсов.';
        editor.append(note);
      } else {
        const options = document.createElement('div');
        options.className = 'member-options';
        const selected = new Set(currentIds);
        candidates.forEach((regimen) => {
          const option = document.createElement('label');
          option.className = 'member-option';
          const input = document.createElement('input');
          input.type = 'checkbox';
          input.value = regimen.id;
          input.checked = selected.has(regimen.id);
          const copy = document.createElement('span');
          copy.className = 'member-option-copy';
          const name = document.createElement('span');
          name.className = 'member-option-name';
          name.append(
            createFormIcon(regimen.medication_form),
            document.createTextNode(regimen.medication_name)
          );
          const dose = document.createElement('span');
          dose.className = 'member-option-dose';
          dose.textContent = `${formatDose(regimen.dose_amount, regimen.dose_unit)}${regimen.status === 'paused' ? ' · на паузе' : ''}`;
          copy.append(name, dose);
          option.append(input, copy);
          options.append(option);
        });
        editor.append(options);
      }

      const actions = document.createElement('div');
      actions.className = 'set-editor-actions';
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'compact-primary';
      save.textContent = state.busySets ? 'Сохраняю…' : 'Сохранить';
      save.disabled = state.busySets || candidates.length === 0;
      save.addEventListener('click', () => saveSetEditor(key));
      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'regimen-button';
      cancel.textContent = 'Отмена';
      cancel.disabled = state.busySets;
      cancel.addEventListener('click', () => {
        state.editingSetKey = null;
        renderMedicationSets();
      });
      actions.append(save, cancel);
      editor.append(actions);
      container.append(editor);
    }

    function renderMedicationSets() {
      const data = state.setsData || { sets: [], regimens: [] };
      const list = byId('set-management-list');
      list.replaceChildren();
      data.sets.forEach((medicationSet) => {
        const row = document.createElement('li');
        row.className = 'managed-set-row';
        const head = document.createElement('div');
        head.className = 'managed-set-head';
        const heading = document.createElement('div');
        const title = document.createElement('h2');
        title.className = 'managed-set-title';
        title.append(
          createIcon(setIconName(medicationSet.name)),
          document.createTextNode(medicationSet.name)
        );
        const windowLabel = document.createElement('p');
        windowLabel.className = 'managed-set-window';
        windowLabel.textContent = `${medicationSet.window_start}–${medicationSet.window_end}`;
        heading.append(title, windowLabel);

        const buttons = document.createElement('div');
        buttons.className = 'section-actions';
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'regimen-button';
        edit.textContent = 'Изменить';
        edit.disabled = state.busySets;
        edit.addEventListener('click', () => {
          state.editingSetKey = state.editingSetKey === medicationSet.id
            ? null : medicationSet.id;
          renderMedicationSets();
        });
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'regimen-button danger';
        remove.textContent = 'Удалить';
        remove.disabled = state.busySets;
        remove.addEventListener('click', () => deleteManagedSet(medicationSet));
        buttons.append(edit, remove);
        head.append(heading, buttons);
        row.append(head);

        const members = document.createElement('ul');
        members.className = 'managed-set-members';
        medicationSet.regimen_ids.forEach((regimenId) => {
          const regimen = data.regimens.find((item) => item.id === regimenId);
          if (!regimen) return;
          const member = document.createElement('li');
          member.append(
            createFormIcon(regimen.medication_form),
            document.createTextNode(
              `${regimen.medication_name} · ${formatDose(regimen.dose_amount, regimen.dose_unit)}`
            )
          );
          members.append(member);
        });
        row.append(members);
        if (state.editingSetKey === medicationSet.id) {
          renderSetEditor(row, medicationSet.id, medicationSet.regimen_ids);
        }
        list.append(row);
      });

      const existingNames = new Set(data.sets.map((item) => item.name.toLocaleLowerCase('ru-RU')));
      const missingPresets = Object.entries(setPresets).filter(
        ([, preset]) => !existingNames.has(preset.name.toLocaleLowerCase('ru-RU'))
      );
      const presetActions = byId('preset-actions');
      presetActions.replaceChildren();
      missingPresets.forEach(([key, preset]) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'regimen-button';
        button.append(createIcon(preset.icon), document.createTextNode(preset.name));
        button.disabled = state.busySets;
        button.addEventListener('click', () => {
          state.editingSetKey = `new:${key}`;
          renderMedicationSets();
        });
        presetActions.append(button);
      });
      const newEditor = byId('new-set-editor');
      newEditor.replaceChildren();
      if (state.editingSetKey?.startsWith('new:')) {
        renderSetEditor(newEditor, state.editingSetKey);
      }
      setVisible('preset-section', missingPresets.length > 0);
      setVisible('sets-loading', false);
      setVisible('sets-empty', data.sets.length === 0);
    }

    async function loadMedicationSets(options = {}) {
      if (!options.silent) setVisible('sets-loading', true);
      byId('sets-error').hidden = true;
      try {
        state.setsData = await request('/mini-app/sets/manage', { init_data: initData });
        renderMedicationSets();
      } catch (error) {
        setVisible('sets-loading', false);
        byId('sets-error').textContent = errorMessage(error);
        byId('sets-error').hidden = false;
      }
    }

    async function saveSetEditor(key) {
      if (state.busySets) return;
      const editor = document.querySelector(`[data-set-editor="${key}"]`);
      const errorElement = byId('sets-error');
      clearFormError(editor, errorElement);
      const regimenIds = [...editor.querySelectorAll('input[type="checkbox"]:checked')]
        .map((input) => input.value);
      if (regimenIds.length === 0) {
        showFormError(editor, errorElement, new Error('Выберите хотя бы один препарат.'));
        return;
      }
      state.busySets = true;
      renderMedicationSets();
      try {
        if (key.startsWith('new:')) {
          await request('/mini-app/sets/create', {
            init_data: initData, preset: key.slice(4), regimen_ids: regimenIds
          });
        } else {
          await request(`/mini-app/sets/${encodeURIComponent(key)}/members`, {
            init_data: initData, regimen_ids: regimenIds
          });
        }
        state.editingSetKey = null;
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus('Состав набора сохранён');
        await Promise.all([loadMedicationSets({ silent: true }), loadDashboard({ silent: true })]);
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        showFormError(editor, errorElement, new Error(
          error.status === 409 ? error.message : errorMessage(error)
        ));
      } finally {
        state.busySets = false;
        renderMedicationSets();
      }
    }

    function confirmSetDelete(medicationSet) {
      const message = `Удалить набор «${medicationSet.name}»? Курсы и их графики сохранятся.`;
      if (tg?.showConfirm) return new Promise((resolve) => tg.showConfirm(message, resolve));
      return Promise.resolve(window.confirm(message));
    }

    async function deleteManagedSet(medicationSet) {
      if (state.busySets || !(await confirmSetDelete(medicationSet))) return;
      state.busySets = true;
      renderMedicationSets();
      setGlobalStatus('Удаляем набор…');
      try {
        await request(`/mini-app/sets/${encodeURIComponent(medicationSet.id)}/delete`, {
          init_data: initData
        });
        state.editingSetKey = null;
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus('Набор удалён, курсы сохранены');
        await Promise.all([loadMedicationSets({ silent: true }), loadDashboard({ silent: true })]);
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(error.status === 404 ? 'Набор уже удалён' : errorMessage(error), true);
        await loadMedicationSets({ silent: true });
      } finally {
        state.busySets = false;
        renderMedicationSets();
      }
    }

    function confirmRegimenAction(regimen, action) {
      if (action !== 'complete') return Promise.resolve(true);
      const message = `Завершить курс «${regimen.medication_name}»? Необработанные приёмы будут отменены.`;
      if (tg?.showConfirm) return new Promise((resolve) => tg.showConfirm(message, resolve));
      return Promise.resolve(window.confirm(message));
    }

    async function applyRegimenAction(regimen, action) {
      if (state.busyRegimenId || !(await confirmRegimenAction(regimen, action))) return;
      state.busyRegimenId = regimen.id;
      setGlobalStatus(action === 'complete' ? 'Завершаем курс…' : 'Обновляем курс…');
      renderRegimens();
      try {
        const updated = await request(`/mini-app/regimens/${encodeURIComponent(regimen.id)}/action`, {
          init_data: initData, action
        });
        const index = state.regimens.findIndex((item) => item.id === updated.id);
        if (index !== -1) state.regimens[index] = updated;
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus(action === 'complete' ? 'Курс завершён' : 'Курс обновлён');
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(error.status === 409
          ? 'Состояние курса уже изменилось. Обновляем данные…'
          : errorMessage(error), true);
        await loadRegimens({ silent: true });
      } finally {
        state.busyRegimenId = null;
        renderRegimens();
      }
    }

    function confirmRegimenDelete(regimen) {
      const message = `Удалить курс «${regimen.medication_name}»? Будут удалены график и вся история приёмов. Это действие нельзя отменить.`;
      if (tg?.showConfirm) return new Promise((resolve) => tg.showConfirm(message, resolve));
      return Promise.resolve(window.confirm(message));
    }

    async function deleteRegimen(regimen) {
      if (state.busyRegimenId || !(await confirmRegimenDelete(regimen))) return;
      state.busyRegimenId = regimen.id;
      setGlobalStatus('Удаляем курс…');
      renderRegimens();
      try {
        await request(`/mini-app/regimens/${encodeURIComponent(regimen.id)}/delete`, {
          init_data: initData
        });
        state.regimens = state.regimens.filter((item) => item.id !== regimen.id);
        state.setsData = null;
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus('Курс удалён');
        await loadDashboard({ silent: true });
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(error.status === 404 ? 'Курс уже удалён' : errorMessage(error), true);
        await loadRegimens({ silent: true });
      } finally {
        state.busyRegimenId = null;
        renderRegimens();
      }
    }

    function localISODate(value = new Date()) {
      const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: state.dashboard.timezone, year: 'numeric', month: '2-digit', day: '2-digit'
      }).formatToParts(value);
      const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
      return `${values.year}-${values.month}-${values.day}`;
    }

    function updateDoseUnits(resetValue = false) {
      const form = byId('regimen-create-form');
      const medicationForm = form.elements.medication_form.value;
      const options = doseUnits[medicationForm] || doseUnits.other;
      const datalist = byId('dose-unit-options');
      datalist.replaceChildren(...options.map((value) => {
        const option = document.createElement('option');
        option.value = value;
        return option;
      }));
      const unit = byId('create-dose-unit');
      if (resetValue || !unit.value) unit.value = options[0];
    }

    function syncCreateForm() {
      const form = byId('regimen-create-form');
      const target = form.elements.reminder_target.value;
      const exact = target === 'exact';
      setVisible('exact-times-field', exact);
      form.elements.times.disabled = !exact;
      form.elements.times.required = exact;

      const schedule = form.elements.schedule_kind.value;
      const interval = schedule === 'interval';
      const weekdays = schedule === 'weekdays';
      setVisible('interval-field', interval);
      setVisible('weekdays-field', weekdays);
      form.elements.every_days.disabled = !interval;
      form.elements.every_days.required = interval;

      const ending = form.elements.ending_kind.value;
      const byCount = ending === 'total_intakes';
      const byDate = ending === 'end_date';
      setVisible('total-intakes-field', byCount);
      setVisible('end-date-field', byDate);
      form.elements.total_intakes.disabled = !byCount;
      form.elements.total_intakes.required = byCount;
      form.elements.end_date.disabled = !byDate;
      form.elements.end_date.required = byDate;
    }

    function resetCreateForm() {
      const form = byId('regimen-create-form');
      form.reset();
      state.editingRegimenId = null;
      byId('regimen-create-title').textContent = 'Новый курс';
      setVisible('regimen-edit-note', false);
      setVisible('keep-reminder-option', false);
      setVisible('unchanged-ending-option', false);
      form.elements.medication_name.disabled = false;
      form.elements.medication_form.disabled = false;
      form.elements.dose_unit.disabled = false;
      form.elements.start_date.disabled = false;
      form.elements.ending_kind.querySelector('option[value="open_ended"]').disabled = false;
      form.elements.ending_kind.value = 'total_intakes';
      form.elements.total_intakes.min = 1;
      byId('save-regimen-button').textContent = 'Сохранить курс';
      const today = localISODate();
      byId('create-start-date').min = today;
      byId('create-start-date').value = today;
      byId('create-end-date').min = today;
      clearFormError(form, byId('regimen-create-error'));
      updateDoseUnits(true);
      syncCreateForm();
    }

    function openCreateRegimen() {
      resetCreateForm();
      setView('create');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async function openEditRegimen(regimen) {
      if (state.busyRegimenId) return;
      state.busyRegimenId = regimen.id;
      setGlobalStatus('Загружаем параметры курса…');
      renderRegimens();
      try {
        const data = await request(`/mini-app/regimens/${encodeURIComponent(regimen.id)}/edit-data`, {
          init_data: initData
        });
        fillEditForm(data);
        setView('create');
        setGlobalStatus('');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(errorMessage(error), true);
      } finally {
        state.busyRegimenId = null;
        renderRegimens();
      }
    }

    function fillEditForm(data) {
      const form = byId('regimen-create-form');
      form.reset();
      state.editingRegimenId = data.id;
      byId('regimen-create-title').textContent = 'Редактирование курса';
      setVisible('regimen-edit-note', true);
      form.elements.medication_name.value = data.medication_name;
      form.elements.medication_form.value = data.medication_form;
      form.elements.dose_amount.value = data.dose_amount;
      form.elements.dose_unit.value = data.dose_unit;
      form.elements.meal_timing.value = data.meal_timing;
      form.elements.start_date.value = data.start_date;
      form.elements.medication_name.disabled = true;
      form.elements.medication_form.disabled = true;
      form.elements.dose_unit.disabled = true;
      form.elements.start_date.disabled = true;
      form.elements.schedule_kind.value = data.schedule_kind;
      form.elements.every_days.value = data.every_days || '';
      form.querySelectorAll('input[name="weekdays"]').forEach((input) => {
        input.checked = data.weekdays.includes(Number(input.value));
      });
      form.elements.times.value = data.times.join(', ');

      setVisible('keep-reminder-option', data.reminder_target === 'keep');
      if (data.reminder_target === 'keep') {
        byId('keep-reminder-label').textContent = `Оставить набор «${data.reminder_label}»`;
      }
      form.querySelector(
        `input[name="reminder_target"][value="${data.reminder_target}"]`
      ).checked = true;

      const unchanged = byId('unchanged-ending-option');
      unchanged.textContent = `Не менять — ${data.ending}`;
      setVisible('unchanged-ending-option', true);
      form.elements.ending_kind.value = 'unchanged';
      form.elements.total_intakes.value = data.remaining_intakes;
      form.elements.total_intakes.min = Math.max(1, data.minimum_remaining_intakes);
      form.elements.end_date.value = data.end_date || '';
      form.elements.end_date.min = localISODate();
      form.elements.ending_kind.querySelector('option[value="open_ended"]').disabled = true;
      clearFormError(form, byId('regimen-create-error'));
      byId('save-regimen-button').textContent = 'Сохранить изменения';
      updateDoseUnits(false);
      syncCreateForm();
    }

    function createRequestBody(form) {
      const data = new FormData(form);
      const scheduleKind = data.get('schedule_kind');
      const weekdays = [...form.querySelectorAll('input[name="weekdays"]:checked')]
        .map((input) => Number(input.value));
      if (scheduleKind === 'weekdays' && weekdays.length === 0) {
        throw fieldError('Выберите хотя бы один день недели.', 'weekdays');
      }
      const times = String(data.get('times') || '').split(',')
        .map((value) => value.trim()).filter(Boolean);
      if (data.get('reminder_target') === 'exact' && times.length === 0) {
        throw fieldError('Укажите хотя бы одно точное время.', 'times');
      }
      return {
        init_data: initData,
        medication_name: data.get('medication_name'),
        medication_form: data.get('medication_form'),
        dose_amount: data.get('dose_amount'),
        dose_unit: data.get('dose_unit'),
        meal_timing: data.get('meal_timing'),
        start_date: data.get('start_date'),
        reminder_target: data.get('reminder_target'),
        schedule_kind: scheduleKind,
        every_days: scheduleKind === 'interval' ? Number(data.get('every_days')) : null,
        weekdays,
        times,
        ending_kind: data.get('ending_kind'),
        total_intakes: data.get('ending_kind') === 'total_intakes'
          ? Number(data.get('total_intakes')) : null,
        end_date: data.get('ending_kind') === 'end_date' ? data.get('end_date') : null
      };
    }

    function editRequestBody(form) {
      const data = new FormData(form);
      const scheduleKind = data.get('schedule_kind');
      const weekdays = [...form.querySelectorAll('input[name="weekdays"]:checked')]
        .map((input) => Number(input.value));
      if (scheduleKind === 'weekdays' && weekdays.length === 0) {
        throw fieldError('Выберите хотя бы один день недели.', 'weekdays');
      }
      const times = String(data.get('times') || '').split(',')
        .map((value) => value.trim()).filter(Boolean);
      const reminderTarget = data.get('reminder_target');
      if (reminderTarget === 'exact' && times.length === 0) {
        throw fieldError('Укажите хотя бы одно точное время.', 'times');
      }
      const endingKind = data.get('ending_kind');
      return {
        init_data: initData,
        dose_amount: data.get('dose_amount'),
        meal_timing: data.get('meal_timing'),
        reminder_target: reminderTarget,
        schedule_kind: scheduleKind,
        every_days: scheduleKind === 'interval' ? Number(data.get('every_days')) : null,
        weekdays,
        times,
        ending_kind: endingKind,
        remaining_intakes: endingKind === 'total_intakes'
          ? Number(data.get('total_intakes')) : null,
        end_date: endingKind === 'end_date' ? data.get('end_date') : null
      };
    }

    async function submitRegimenForm(event) {
      event.preventDefault();
      if (state.busyCreate) return;
      const form = event.currentTarget;
      const errorElement = byId('regimen-create-error');
      const editingId = state.editingRegimenId;
      clearFormError(form, errorElement);
      let body;
      try {
        body = editingId ? editRequestBody(form) : createRequestBody(form);
      } catch (error) {
        showFormError(form, errorElement, error);
        return;
      }
      state.busyCreate = true;
      const button = byId('save-regimen-button');
      button.disabled = true;
      button.textContent = 'Сохраняю…';
      try {
        const result = await request(editingId
          ? `/mini-app/regimens/${encodeURIComponent(editingId)}/edit`
          : '/mini-app/regimens/create', body);
        state.regimens = null;
        await loadDashboard({ silent: true });
        await loadRegimens();
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus(editingId
          ? `Изменения сохранены · ${result.events_count} будущих приёмов обновлено`
          : `Курс сохранён · ${result.events_count} приёмов запланировано`);
        setView('regimens');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        showFormError(form, errorElement, new Error(
          error.status === 422 || error.status === 409 ? error.message : errorMessage(error)
        ));
      } finally {
        state.busyCreate = false;
        button.disabled = false;
        button.textContent = editingId ? 'Сохранить изменения' : 'Сохранить курс';
      }
    }

    function renderDashboard() {
      byId('timezone-label').textContent = state.dashboard.timezone;
      const canManagePersonal = state.dashboard.can_manage_personal_regimens;
      setVisible('add-regimen-button', canManagePersonal);
      setVisible('empty-add-regimen-button', canManagePersonal);
      setVisible('manage-sets-button', canManagePersonal);
      renderSummary();
      renderToday();
      renderHistory();
      renderSettings();
      showOnly('app');
      setView(state.view);
    }

    function syncSettingsForm() {
      byId('repeat-field').disabled = !byId('reminders-enabled').checked;
    }

    function renderSettings() {
      const settings = state.dashboard.settings;
      const form = byId('settings-form');
      form.elements.reminders_enabled.checked = settings.reminders_enabled;
      const repeat = form.querySelector(
        `input[name="repeat_minutes"][value="${settings.repeat_minutes}"]`
      );
      if (repeat) repeat.checked = true;
      byId('settings-timezone').textContent = state.dashboard.timezone;
      const canUpdateTimezone = Boolean(detectedZone && detectedZone !== state.dashboard.timezone);
      byId('detected-timezone-note').textContent = canUpdateTimezone
        ? `На устройстве определён ${detectedZone}.`
        : 'Совпадает с часовым поясом устройства.';
      const timezoneButton = byId('update-timezone-button');
      timezoneButton.textContent = canUpdateTimezone ? `Сменить на ${detectedZone}` : '';
      timezoneButton.hidden = !canUpdateTimezone;
      clearFormError(form, byId('settings-error'));
      syncSettingsForm();
    }

    async function saveSettings(event) {
      event.preventDefault();
      if (state.busySettings) return;
      const form = event.currentTarget;
      const errorElement = byId('settings-error');
      clearFormError(form, errorElement);
      const repeatMinutes = Number(new FormData(form).get('repeat_minutes'));
      state.busySettings = true;
      byId('save-settings-button').disabled = true;
      byId('save-settings-button').textContent = 'Сохраняю…';
      try {
        state.dashboard.settings = await request('/mini-app/settings', {
          init_data: initData,
          repeat_minutes: repeatMinutes,
          reminders_enabled: form.elements.reminders_enabled.checked
        });
        tg?.HapticFeedback?.notificationOccurred('success');
        setGlobalStatus('Настройки сохранены');
        renderSettings();
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        showFormError(form, errorElement, new Error(
          error.status === 422 ? error.message : errorMessage(error)
        ));
      } finally {
        state.busySettings = false;
        byId('save-settings-button').disabled = false;
        byId('save-settings-button').textContent = 'Сохранить настройки';
      }
    }

    async function updateSettingsTimezone() {
      if (state.busySettings || !detectedZone) return;
      state.busySettings = true;
      const button = byId('update-timezone-button');
      button.disabled = true;
      button.textContent = 'Обновляю…';
      setGlobalStatus('Обновляем часовой пояс…');
      try {
        await request('/mini-app/timezone', { init_data: initData, timezone: detectedZone });
        tg?.HapticFeedback?.notificationOccurred('success');
        await loadDashboard({ silent: true });
        setGlobalStatus('Часовой пояс обновлён');
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(errorMessage(error), true);
      } finally {
        state.busySettings = false;
        button.disabled = false;
      }
    }

    async function loadDashboard(options = {}) {
      if (!options.silent) showOnly('loading');
      setGlobalStatus('');
      try {
        const dashboard = await request('/mini-app/dashboard', {
          init_data: initData, history_days: state.historyDays
        });
        state.dashboard = dashboard;
        if (!dashboard.timezone) {
          byId('zone').textContent = `Определён часовой пояс: ${detectedZone}`;
          showOnly('setup');
          return;
        }
        renderDashboard();
      } catch (error) {
        if (options.silent && state.dashboard) {
          setGlobalStatus(errorMessage(error), true);
          return;
        }
        byId('error-copy').textContent = errorMessage(error);
        showOnly('error');
      }
    }

    async function saveTimezone() {
      const button = byId('save-timezone');
      button.disabled = true;
      button.textContent = 'Сохраняю…';
      setGlobalStatus('');
      try {
        await fetch('/mini-app/timezone', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData, timezone: detectedZone })
        }).then(async (response) => {
          if (!response.ok) {
            const error = new Error('Timezone request failed');
            error.status = response.status;
            throw error;
          }
        });
        tg?.HapticFeedback?.notificationOccurred('success');
        await loadDashboard();
      } catch (error) {
        setGlobalStatus(errorMessage(error), true);
      } finally {
        button.disabled = false;
        button.textContent = 'Использовать этот часовой пояс';
      }
    }

    function confirmSkip(event) {
      const message = `Пропустить приём «${event.medication_name}»?`;
      if (tg?.showConfirm) {
        return new Promise((resolve) => tg.showConfirm(message, resolve));
      }
      return Promise.resolve(window.confirm(message));
    }

    function confirmHistoricalTake(event) {
      if (!correctableStatuses.has(event.status)) return Promise.resolve(true);
      const action = event.medication_form === 'injection' ? 'укол был сделан' : 'препарат был принят';
      const message = `Подтвердить, что «${event.medication_name}» — ${action}? История будет исправлена.`;
      if (tg?.showConfirm) return new Promise((resolve) => tg.showConfirm(message, resolve));
      return Promise.resolve(window.confirm(message));
    }

    async function applyAction(event, action, minutes = null, editing = false) {
      if (state.busyEventId || state.busySetId) return;
      if (action === 'skip' && !(await confirmSkip(event))) return;
      if (action === 'take' && !editing && !(await confirmHistoricalTake(event))) return;
      state.busyEventId = event.id;
      const progress = action === 'undo' ? 'Отменяем приём…' : action === 'take'
        ? 'Отмечаем приём…'
        : (action === 'snooze' ? 'Откладываем напоминание…' : 'Отмечаем пропуск…');
      setGlobalStatus(progress);
      renderSummary();
      renderToday();
      if (byId('intake-editor-dialog').open) renderIntakeEditor();
      try {
        const result = await request(`/mini-app/events/${encodeURIComponent(event.id)}/action`, {
          init_data: initData, action, minutes
        });
        event.status = result.status;
        event.taken_at = result.taken_at;
        state.snoozeEventId = null;
        tg?.HapticFeedback?.notificationOccurred('success');
        const success = action === 'undo' ? 'Приём отменён — можно принять заново' : action === 'take'
          ? 'Приём отмечен'
          : (action === 'snooze' ? `Напоминание отложено на ${minutes} мин` : 'Пропуск отмечен');
        setGlobalStatus(success);
        await loadDashboard({ silent: true });
      } catch (error) {
        tg?.HapticFeedback?.notificationOccurred('error');
        setGlobalStatus(error.status === 409
          ? 'Статус уже изменился. Обновляем данные…'
          : errorMessage(error), true);
        await loadDashboard({ silent: true });
      } finally {
        state.busyEventId = null;
        if (state.dashboard) {
          renderSummary();
          renderToday();
          if (byId('intake-editor-dialog').open) renderIntakeEditor();
        }
      }
    }

    function moveTabIndicator(tab, animate = true) {
      const tabs = byId('main-tabs');
      const indicator = byId('tab-indicator');
      if (!tab || tabs.hidden) return;

      const tabsRect = tabs.getBoundingClientRect();
      const indicatorRect = indicator.getBoundingClientRect();
      const currentLeft = indicatorRect.left - tabsRect.left;
      const currentWidth = indicatorRect.width;
      const targetLeft = tab.offsetLeft;
      const targetWidth = tab.offsetWidth;
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const shouldAnimate = animate && !reducedMotion && currentWidth > 0
        && Math.abs(currentLeft - targetLeft) > 1;

      indicator.getAnimations?.().forEach((animation) => animation.cancel());
      indicator.style.left = `${targetLeft}px`;
      indicator.style.width = `${targetWidth}px`;
      if (!shouldAnimate || !indicator.animate) return;

      indicator.animate([
        { left: `${currentLeft}px`, width: `${currentWidth}px` },
        { left: `${targetLeft}px`, width: `${targetWidth}px` }
      ], {
        duration: 140,
        easing: 'cubic-bezier(.2, 0, 0, 1)'
      });
    }

    function setView(view) {
      const viewChanged = state.view !== view;
      state.view = view;
      const today = view === 'today';
      const history = view === 'history';
      const regimens = view === 'regimens';
      const family = view === 'family';
      const sets = view === 'sets';
      const settings = view === 'settings';
      const create = view === 'create';
      byId('today-tab').setAttribute('aria-current', today ? 'page' : 'false');
      byId('history-tab').setAttribute('aria-current', history ? 'page' : 'false');
      byId('regimens-tab').setAttribute('aria-current', regimens ? 'page' : 'false');
      byId('family-tab').setAttribute('aria-current', family ? 'page' : 'false');
      byId('settings-button').setAttribute('aria-pressed', String(settings));
      setVisible('dashboard-summary', today);
      setVisible('main-tabs', today || history || regimens || family);
      setVisible('today-panel', today);
      setVisible('history-panel', history);
      setVisible('regimens-panel', regimens);
      setVisible('family-panel', family);
      setVisible('sets-panel', sets);
      setVisible('settings-panel', settings);
      setVisible('regimen-create-panel', create);
      const activeTab = today ? byId('today-tab') : history ? byId('history-tab')
        : regimens ? byId('regimens-tab') : family ? byId('family-tab') : null;
      moveTabIndicator(activeTab, viewChanged);
      if (regimens && state.regimens === null) loadRegimens();
      if (family && state.family === null) loadFamily();
      if (sets && state.setsData === null) loadMedicationSets();
      if (today) tg?.BackButton?.hide(); else tg?.BackButton?.show();
      if (viewChanged && activeTab) tg?.HapticFeedback?.selectionChanged();
      if (viewChanged) {
        const viewMeta = {
          today: ['Сегодня', 'today-title'], history: ['История', 'history-title'],
          regimens: ['Курсы', 'regimens-title'], family: ['Семья', 'family-title'],
          sets: ['Наборы', 'sets-title'], settings: ['Настройки', 'settings-title'],
          create: [state.editingRegimenId ? 'Редактирование курса' : 'Новый курс', 'regimen-create-title']
        }[view];
        document.title = viewMeta ? `${viewMeta[0]} · Вовремя` : 'Вовремя';
        window.scrollTo({ top: 0, behavior: 'auto' });
        const heading = viewMeta ? byId(viewMeta[1]) : null;
        window.requestAnimationFrame(() => heading?.focus({ preventScroll: true }));
      }
    }

    window.addEventListener('resize', () => {
      window.requestAnimationFrame(() => {
        moveTabIndicator(document.querySelector('.tab[aria-current="page"]'), false);
      });
    });

    byId('today-tab').addEventListener('click', () => setView('today'));
    byId('edit-intakes-button').addEventListener('click', () => {
      renderIntakeEditor();
      byId('intake-editor-dialog').showModal();
    });
    byId('intake-editor-close').addEventListener('click', () => byId('intake-editor-dialog').close());
    byId('history-tab').addEventListener('click', () => setView('history'));
    byId('open-report-button').addEventListener('click', openReport);
    byId('report-form').addEventListener('submit', generateReport);
    byId('report-cancel').addEventListener('click', () => byId('report-dialog').close());
    byId('report-download').addEventListener('click', downloadReport);
    byId('regimens-tab').addEventListener('click', () => setView('regimens'));
    byId('family-tab').addEventListener('click', () => setView('family'));
    byId('refresh-family-button').addEventListener('click', () => loadFamily({ silent: true }));
    byId('invite-family-button').addEventListener('click', () => inviteFamilyMember());
    byId('empty-invite-family-button').addEventListener('click', () => inviteFamilyMember());
    byId('family-dialog-cancel').addEventListener('click', () => byId('family-dialog').close('cancel'));
    byId('family-invite-cancel').addEventListener('click', () => byId('family-invite-dialog').close('cancel'));
    byId('settings-button').addEventListener('click', () => {
      setView(state.view === 'settings' ? 'today' : 'settings');
    });
    byId('settings-form').addEventListener('submit', saveSettings);
    byId('reminders-enabled').addEventListener('change', syncSettingsForm);
    byId('update-timezone-button').addEventListener('click', updateSettingsTimezone);
    byId('add-regimen-button').addEventListener('click', openCreateRegimen);
    byId('empty-add-regimen-button').addEventListener('click', openCreateRegimen);
    byId('manage-sets-button').addEventListener('click', () => setView('sets'));
    byId('cancel-sets').addEventListener('click', () => setView('regimens'));
    byId('cancel-regimen-create').addEventListener('click', () => setView('regimens'));
    byId('regimen-create-form').addEventListener('submit', submitRegimenForm);
    byId('create-medication-form').addEventListener('change', () => updateDoseUnits(true));
    byId('create-schedule-kind').addEventListener('change', syncCreateForm);
    byId('create-ending-kind').addEventListener('change', syncCreateForm);
    byId('create-start-date').addEventListener('change', () => {
      byId('create-end-date').min = byId('create-start-date').value;
    });
    document.querySelectorAll('input[name="reminder_target"]').forEach((input) => {
      input.addEventListener('change', syncCreateForm);
    });
    byId('retry-button').addEventListener('click', bootstrap);
    byId('save-timezone').addEventListener('click', saveTimezone);
    document.querySelectorAll('.period-button').forEach((button) => {
      button.addEventListener('click', async () => {
        const days = Number(button.dataset.days);
        if (days === state.historyDays) return;
        state.historyDays = days;
        document.querySelectorAll('.period-button').forEach((item) => {
          item.setAttribute('aria-pressed', String(item === button));
          item.disabled = true;
        });
        await loadDashboard({ silent: true });
        document.querySelectorAll('.period-button').forEach((item) => { item.disabled = false; });
      });
    });
    tg?.BackButton?.onClick(() => {
      setView(state.view === 'create' || state.view === 'sets' ? 'regimens' : 'today');
    });
    let refreshingWindow = false;
    async function refreshCurrentWindow() {
      if (document.hidden || state.view !== 'today' || !state.dashboard || refreshingWindow
          || state.busyEventId || state.busySetId || document.querySelector('dialog[open]')) return;
      refreshingWindow = true;
      try {
        await loadDashboard({ silent: true });
      } finally {
        refreshingWindow = false;
      }
    }
    setInterval(refreshCurrentWindow, 60_000);
    document.addEventListener('visibilitychange', refreshCurrentWindow);
    bootstrap();
  </script>
</body>
</html>
"""
