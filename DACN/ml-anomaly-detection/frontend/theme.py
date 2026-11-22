"""Shared presentation theme for monitoring and the retained CSV workspaces."""
from __future__ import annotations

import streamlit as st


def apply_style(dark: bool) -> None:
    """Apply scoped dashboard styling without changing native widget behavior."""
    palette = {
        "bg": "#0b1220", "surface": "#111c2e", "raised": "#17243a",
        "text": "#e8eef8", "muted": "#a7b7ce", "line": "#2a3c56",
        "accent": "#8cb6ff", "soft": "#182e4e", "scheme": "dark",
        "shadow": "0 5px 20px rgba(0, 0, 0, .12)",
        "watch_soft": "#1c293e", "warning_soft": "#332a18", "critical_soft": "#36202b",
        "warning": "#fbbf24", "critical": "#fda4af", "watch": "#adbed6",
        "success": "#6ee7b7", "success_soft": "#14332f",
    } if dark else {
        "bg": "#f4f7fb", "surface": "#ffffff", "raised": "#f8fafc",
        "text": "#14243c", "muted": "#607089", "line": "#dce5f0",
        "accent": "#2563eb", "soft": "#edf4ff", "scheme": "light",
        "shadow": "0 5px 20px rgba(27, 52, 86, .045)",
        "watch_soft": "#f0f4f8", "warning_soft": "#fff8e7", "critical_soft": "#fff0f2",
        "warning": "#a16207", "critical": "#be123c", "watch": "#52657e",
        "success": "#047857", "success_soft": "#edf9f3",
    }
    css = r"""
    <style>
    :root, .stApp, [data-testid="stSidebar"] {
        --page-bg:__BG__; --surface:__SURFACE__; --surface-raised:__RAISED__;
        --ink:__TEXT__; --muted:__MUTED__; --line:__LINE__;
        --accent:__ACCENT__; --soft:__SOFT__; --card-shadow:__SHADOW__;
        --watch:__WATCH__; --watch-soft:__WATCH_SOFT__;
        --warning:__WARNING__; --warning-soft:__WARNING_SOFT__;
        --critical:__CRITICAL__; --critical-soft:__CRITICAL_SOFT__;
        --success:__SUCCESS__; --success-soft:__SUCCESS_SOFT__;
        --primary-color:#2563eb; --text-color:__TEXT__;
        --background-color:__BG__; --secondary-background-color:__RAISED__;
        color-scheme:__SCHEME__;
    }
    .stApp {
        background:var(--page-bg); color:var(--ink);
        font-family:Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
        font-size:16px;
    }
    [data-testid="stHeader"] {background:var(--page-bg);}
    .block-container {max-width:1480px; padding:2rem 2rem 3rem;}
    [data-testid="stSidebar"] {background:var(--surface); border-right:1px solid var(--line);}
    [data-testid="stSidebarContent"] {padding-top:1.25rem;}
    [data-testid="stSidebar"] .block-container {padding:1rem 1.1rem 2rem;}
    [data-testid="stSidebar"] hr {margin:1.1rem 0;}
    [data-testid="stExpandSidebarButton"] button,
    [data-testid="stSidebarCollapseButton"] button,
    button[aria-label="Expand sidebar"], button[aria-label="Collapse sidebar"] {color:var(--ink);}

    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color:var(--ink);}
    [data-testid="stMarkdownContainer"] p {font-size:1rem; line-height:1.65;}
    [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4 {
        color:var(--ink); letter-spacing:-.025em; line-height:1.25;
    }
    [data-testid="stMarkdownContainer"] h1 {font-size:clamp(1.7rem, 2.8vw, 2.3rem); font-weight:750;}
    [data-testid="stMarkdownContainer"] h2 {font-size:1.35rem; font-weight:700; padding-top:.4rem;}
    [data-testid="stMarkdownContainer"] h3 {font-size:1.12rem; font-weight:700;}
    [data-testid="stMarkdownContainer"] h4 {font-size:1rem; font-weight:700;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
    [data-testid="stCaptionContainer"] [data-testid="stMarkdownContainer"] {
        color:var(--muted); font-size:.84rem; line-height:1.55;
    }
    [data-testid="stWidgetLabel"] p {font-size:.88rem; font-weight:600; line-height:1.45;}
    [data-testid="stMarkdownContainer"] a {color:var(--accent); text-underline-offset:3px;}
    hr {border-color:var(--line); margin:1.35rem 0;}

    .workspace-header {
        display:flex; align-items:center; justify-content:space-between;
        gap:1.25rem; padding:.4rem 0 1.55rem; margin-bottom:.1rem;
    }
    .workspace-kicker, .section-kicker {
        color:var(--accent); font-size:.75rem; font-weight:750;
        letter-spacing:.11em; text-transform:uppercase; margin-bottom:.45rem;
    }
    .workspace-header h1 {margin:0 0 .55rem; font-weight:750;}
    .workspace-subtitle {color:var(--muted); margin:0; max-width:760px; font-size:.95rem; line-height:1.65;}
    .header-tags {display:flex; align-items:center; justify-content:flex-end; flex-wrap:wrap; gap:.5rem; max-width:380px;}
    .header-tags > span, .inline-badge {
        display:inline-flex; align-items:center; gap:.4rem; padding:.35rem .65rem;
        background:var(--soft); color:var(--accent); border:1px solid var(--line);
        border-radius:8px; font-size:.875rem; font-weight:650; line-height:1.4;
        white-space:normal;
    }
    .section-heading {
        display:flex; align-items:flex-end; justify-content:space-between;
        gap:1rem; margin:1.25rem 0 .85rem;
    }
    .section-heading h2, .section-heading h3 {margin:0; padding:0;}
    .section-heading p, .section-heading > span {color:var(--muted); margin:.35rem 0 0; font-size:.875rem;}
    .section-kicker {margin-bottom:.25rem;}
    .page-help {color:var(--muted); font-size:.88rem; line-height:1.65; margin:.35rem 0 1rem; max-width:90ch;}
    .source-notice {
        display:flex; flex-wrap:wrap; align-items:center; gap:.35rem .7rem;
        background:var(--soft); border:1px solid var(--line); border-radius:10px;
        padding:11px 14px; margin:.25rem 0 .7rem; color:var(--ink);
        font-size:.86rem; line-height:1.6; overflow-wrap:anywhere;
    }
    .source-notice strong {font-size:.86rem; font-weight:700;}
    .source-notice > span:last-child, .source-notice p {color:var(--muted); margin:0; font-size:.84rem; line-height:1.6;}
    .source-notice.source-live {background:var(--success-soft);}
    .source-notice.source-live strong, .source-live .status-dot {color:var(--success);}
    .source-notice.source-simulated {background:var(--warning-soft);}
    .source-notice.source-simulated strong, .source-simulated .status-dot {color:var(--warning);}
    .source-notice.source-waiting, .source-notice.source-unknown {background:var(--surface-raised);}
    .status-dot {display:inline-block; flex:0 0 8px; width:8px; height:8px; border-radius:50%; background:currentColor; color:var(--muted);}
    .workflow-note {padding:12px 15px; background:var(--surface-raised); color:var(--muted); border:1px solid var(--line); border-radius:10px; font-size:.87rem; line-height:1.65; margin:.5rem 0 1rem;}
    .workflow-note strong {color:var(--ink);}

    .health-grid {display:grid; grid-template-columns:repeat(auto-fit, minmax(185px, 1fr)); gap:12px; margin:.4rem 0 1rem;}
    .health-cell {
        min-width:0; background:var(--surface); border:1px solid var(--line);
        border-radius:12px; padding:15px 18px; box-shadow:var(--card-shadow);
    }
    .health-label {display:block; color:var(--muted); font-size:.875rem; font-weight:650; margin-bottom:.35rem;}
    .health-value {display:block; color:var(--ink); font-size:1rem; font-weight:700; line-height:1.4; overflow-wrap:anywhere;}
    .health-meta {display:block; color:var(--muted); font-size:.875rem; line-height:1.5; margin-top:.3rem; overflow-wrap:anywhere;}
    .status-note {
        background:var(--soft); border:1px solid var(--line); border-left:3px solid var(--accent);
        border-radius:10px; color:var(--ink); padding:12px 15px; font-size:.87rem; line-height:1.6;
        margin:.45rem 0 .9rem;
    }
    .level-watch {--level:var(--watch); --level-soft:var(--watch-soft);}
    .level-warning {--level:var(--warning); --level-soft:var(--warning-soft);}
    .level-critical {--level:var(--critical); --level-soft:var(--critical-soft);}
    .inline-badge.level-watch, .inline-badge.level-warning, .inline-badge.level-critical {
        background:var(--level-soft); color:var(--level);
    }
    .health-value.level-watch, .health-value.level-warning, .health-value.level-critical {color:var(--level);}
    .status-note.level-watch, .status-note.level-warning, .status-note.level-critical {
        background:var(--level-soft); border-left-color:var(--level);
    }
    .alert-summary {
        border:1px solid var(--line); border-left:4px solid var(--level, var(--accent));
        border-radius:12px; background:var(--level-soft, var(--surface));
        padding:15px 18px; margin:.7rem 0 .2rem;
    }
    .alert-summary-title {display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:.5rem; color:var(--ink); font-size:1rem; font-weight:750; line-height:1.5; margin:0 0 .35rem;}
    .alert-summary-title .inline-badge {background:var(--surface); color:var(--level, var(--accent)); border-color:var(--line);}
    .alert-summary-meta {color:var(--muted); font-size:.875rem; line-height:1.55; overflow-wrap:anywhere;}
    .alert-summary-voters {color:var(--ink); font-size:.875rem; line-height:1.55; margin-top:.5rem;}
    .incident-counts {display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin:.6rem 0 1rem;}
    .incident-count {display:flex; flex-direction:row; align-items:center; gap:.7rem; padding:10px 14px; border:1px solid var(--line); border-radius:10px; background:var(--level-soft); color:var(--level);}
    .incident-count strong {font-size:1.4rem; line-height:1.2; font-weight:750;}
    .incident-count span {font-size:.875rem; line-height:1.5; font-weight:650;}
    .guide-grid {display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; margin:.75rem 0 1rem;}
    .guide-card {background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:18px; min-width:0;}
    .guide-card strong {display:block; color:var(--ink); font-size:.94rem; margin-bottom:.5rem;}
    .guide-card p {color:var(--muted); font-size:.85rem; line-height:1.6; margin:0;}
    .vote-guide {display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; color:var(--muted); font-size:.8rem; line-height:1.6; margin:.7rem 0;}
    .vote-guide > span {display:inline-flex; align-items:center; gap:6px;}

    [data-testid="stMetric"] {
        min-height:132px; background:var(--surface); border:1px solid var(--line);
        border-radius:14px; padding:18px 20px; box-shadow:var(--card-shadow);
    }
    [data-testid="stMetricLabel"] p {font-size:.875rem; font-weight:650; color:var(--muted); line-height:1.4;}
    [data-testid="stMetricValue"] {font-size:clamp(1.5rem, 2.3vw, 1.95rem); font-weight:750; line-height:1.3; letter-spacing:-.025em;}
    [data-testid="stMetricDelta"] {font-size:.76rem; color:var(--muted); margin-top:.35rem;}
    .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {
        display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:14px;
    }
    .st-key-monitor_metrics [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        width:auto !important; min-width:0 !important; flex:unset !important;
    }
    .st-key-monitor_metrics [class*="st-key-monitor_metric_"] {
        background:var(--surface); border:1px solid var(--line); border-radius:14px;
        box-shadow:var(--card-shadow); gap:.1rem; overflow:hidden;
    }
    .st-key-monitor_metrics [data-testid="stMetric"] {min-height:110px; border:0; background:transparent; box-shadow:none; border-radius:0; padding:16px 16px 5px;}
    .st-key-monitor_metrics [class*="st-key-monitor_metric_"]:has(.is-deviating) {border-color:var(--warning); box-shadow:inset 0 3px 0 var(--warning);}
    .metric-context {padding:0 16px 14px; display:flex; flex-direction:column; gap:.45rem;}
    .metric-state {display:inline-flex; align-self:flex-start; border-radius:5px; font-size:.74rem; line-height:1.5; font-weight:650; padding:3px 6px; color:var(--muted); background:var(--surface-raised);}
    .metric-state.is-deviating, .metric-state.is-outside {color:var(--warning); background:var(--warning-soft);}
    .metric-description {font-size:.75rem; line-height:1.5; color:var(--muted);}
    .st-key-monitor_control_columns > [data-testid="stHorizontalBlock"],
    .st-key-monitor_control_columns > div > [data-testid="stHorizontalBlock"] {gap:22px;}
    .st-key-monitor_dashboard .health-grid {grid-template-columns:repeat(2, minmax(0, 1fr));}
    .st-key-monitor_dashboard .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {grid-template-columns:repeat(3, minmax(0, 1fr));}
    .st-key-monitor_dashboard [data-testid="stChatMessage"] {padding:12px;}
    .st-key-monitor_dashboard [data-testid="stChatMessage"] p {font-size:.88rem; line-height:1.6;}
    #bot-canh-bao {scroll-margin-top:5rem;}
    [data-testid="stVerticalBlockBorderWrapper"] > div {border-color:var(--line) !important; border-radius:14px;}
    [data-testid="stForm"] {background:var(--surface); border-color:var(--line); border-radius:12px; padding:16px;}
    [data-testid="stExpander"] {
        color:var(--ink); background:var(--surface); border-color:var(--line);
        border-radius:12px; box-shadow:none;
    }
    [data-testid="stExpander"] summary {min-height:46px; padding-top:.65rem; padding-bottom:.65rem;}
    [data-testid="stExpander"] summary p {font-size:.87rem; font-weight:600;}
    [data-testid="stDataFrame"], [data-testid="stTable"] {border:1px solid var(--line); border-radius:12px; overflow:hidden;}
    [data-testid="stPlotlyChart"] {background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:8px 3px; overflow:hidden;}

    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button,
    [data-testid="stFormSubmitButton"] button {min-height:44px; border-radius:9px; font-weight:650; transition:background-color .15s, border-color .15s, box-shadow .15s;}
    [data-testid="stBaseButton-primary"] {background:#2563eb; border:1px solid #2563eb; color:#ffffff; box-shadow:0 3px 8px rgba(37, 99, 235, .13);}
    [data-testid="stBaseButton-primary"]:hover {background:#1d4ed8; border-color:#1d4ed8; color:#ffffff;}
    [data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"],
    [data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"] p {color:#ffffff;}
    [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] button {
        background:var(--surface); color:var(--ink); border:1px solid var(--line);
    }
    [data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover {
        background:var(--soft); color:var(--accent); border-color:var(--accent);
    }
    button:disabled {opacity:.48; cursor:not-allowed;}
    .stApp :is(button, input, textarea, [role="button"]):focus-visible {
        outline:3px solid var(--accent); outline-offset:3px;
    }
    [data-baseweb="select"] > div, [data-baseweb="input"] > div,
    [data-baseweb="popover"] ul {background:var(--surface); color:var(--ink); border-color:var(--line); border-radius:9px;}
    [data-testid="stSelectbox"] .react-aria-ComboBox > [role="group"],
    [data-testid="stMultiSelect"] .react-aria-ComboBox > [role="group"] {
        min-height:44px; background:var(--surface); color:var(--ink); border:1px solid var(--line); border-radius:9px;
    }
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input {
        color:var(--ink); background:transparent; font-size:.9rem;
    }
    [data-testid="stSelectbox"] input:disabled, [data-testid="stSelectbox"] [data-disabled] input {
        color:var(--muted); -webkit-text-fill-color:var(--muted); opacity:1;
    }
    [data-testid="stSelectbox"] button, [data-testid="stMultiSelect"] button {color:var(--muted);}
    [data-testid="stMultiSelect"] [data-tag] {background:var(--soft); color:var(--accent);}
    [role="listbox"], [role="option"] {background:var(--surface); color:var(--ink);}
    [role="option"][data-focused], [role="option"][aria-selected="true"] {background:var(--soft); color:var(--accent);}
    [data-testid="stTooltipIcon"] button {color:var(--muted);}
    [data-testid="stFileUploaderDropzone"] {background:var(--surface-raised); color:var(--ink); border:1px dashed var(--line); border-radius:12px; padding:22px 16px;}
    [data-testid="stAlert"] {border-radius:11px; font-size:.89rem;}
    [role="tab"] {min-height:44px; color:var(--muted); font-weight:600;}
    [role="tab"][aria-selected="true"] {color:var(--accent);}
    [role="tablist"] {overflow-x:auto; gap:.35rem;}
    [data-testid="stDialog"] [role="dialog"] {background:var(--surface); color:var(--ink); border:1px solid var(--line); border-radius:16px;}
    [data-testid="stChatMessage"] {border:1px solid var(--line); background:var(--surface-raised); border-radius:12px;}
    [data-testid="stChatInput"] {border-color:var(--line); border-radius:12px;}

    /* The alert bot is one conversation, with native, accessible chat controls. */
    .st-key-alert_chat_panel {
        background:var(--surface); border:1px solid var(--line) !important;
        border-radius:20px !important; box-shadow:var(--card-shadow); min-width:0;
    }
    .st-key-alert_chat_panel .messenger-header {
        display:flex; align-items:center; gap:12px; padding:14px;
        background:var(--soft); border:1px solid var(--line); border-radius:14px;
    }
    .st-key-alert_chat_panel .messenger-avatar {
        display:grid; place-items:center; flex:0 0 42px; width:42px; height:42px;
        border-radius:14px; background:var(--accent); color:var(--surface);
        font-size:16px; font-weight:800; line-height:1;
    }
    .st-key-alert_chat_panel .messenger-title,
    .st-key-alert_chat_panel .messenger-header h3,
    .st-key-alert_chat_panel .messenger-header strong {
        display:block; color:var(--ink); margin:0; padding:0; font-size:17px;
        line-height:1.4; font-weight:750; letter-spacing:-.02em;
    }
    .st-key-alert_chat_panel .messenger-subtitle {
        display:block; color:var(--muted); font-size:13px; line-height:1.5; margin:3px 0 0;
    }
    .st-key-alert_chat_panel .messenger-action {
        margin-left:auto; color:var(--accent); font-size:13px; font-weight:650;
        line-height:1.5; text-align:right;
    }
    .st-key-alert_chat_panel .messenger-status {
        display:flex; align-items:flex-start; gap:8px; color:var(--muted);
        font-size:13px; line-height:1.6; padding:0 3px; overflow-wrap:anywhere;
    }
    .st-key-alert_chat_panel .messenger-status .status-dot {margin-top:7px;}
    .st-key-alert_chat_panel .messenger-status.source-live,
    .st-key-alert_chat_panel .messenger-status.status-live {color:var(--success);}
    .st-key-alert_chat_panel .messenger-status.source-simulated,
    .st-key-alert_chat_panel .messenger-status.status-simulated,
    .st-key-alert_chat_panel .messenger-status.status-stale {color:var(--warning);}
    .st-key-alert_chat_panel .messenger-status.status-error {color:var(--critical);}
    .st-key-alert_chat_panel .st-key-alert_chat_timeline {
        background:var(--surface-raised); border:1px solid var(--line); border-radius:16px;
        padding:14px 12px; overscroll-behavior:contain; overflow-x:hidden;
        scrollbar-width:thin; scrollbar-color:var(--line) transparent;
    }
    .st-key-alert_chat_panel [data-testid="stChatMessage"] {
        display:flex; align-items:flex-end; gap:9px; width:100%; min-width:0;
        padding:5px 0; border:0; border-radius:0; background:transparent;
    }
    .st-key-alert_chat_panel [data-testid^="stChatMessageAvatar"] {
        flex:0 0 28px; width:28px; height:28px; border-radius:50%;
        background:var(--soft); color:var(--accent); font-size:16px;
    }
    .st-key-alert_chat_panel [data-testid^="stChatMessageAvatar"] svg {width:17px; height:17px;}
    .st-key-alert_chat_panel [data-testid="stChatMessageContent"] {
        flex:0 1 auto; width:auto; min-width:0; max-width:calc(100% - 37px);
    }
    .st-key-alert_chat_panel .messenger-bubble {
        width:fit-content; max-width:100%; padding:12px 14px;
        background:var(--surface); color:var(--ink); border:1px solid var(--line);
        border-radius:16px 16px 16px 5px; font-size:14px; line-height:1.65;
        overflow-wrap:anywhere; word-break:normal;
    }
    .st-key-alert_chat_panel .messenger-bubble p {font-size:14px; line-height:1.65; margin:0 0 .55rem;}
    .st-key-alert_chat_panel .messenger-bubble p:last-child {margin-bottom:0;}
    .st-key-alert_chat_panel .bubble-bot {background:var(--surface);}
    .st-key-alert_chat_panel .bubble-alert {border-left:3px solid var(--warning);}
    .st-key-alert_chat_panel .bubble-alert:has(.badge-critical) {border-left-color:var(--critical);}
    .st-key-alert_chat_panel [data-testid="stChatMessage"]:has(.bubble-user) {flex-direction:row-reverse;}
    .st-key-alert_chat_panel .bubble-user {
        margin-left:auto; background:#2563eb; color:#ffffff; border-color:#2563eb;
        border-radius:16px 16px 5px 16px;
    }
    .st-key-alert_chat_panel .bubble-user :is(p, li, strong, em, a) {color:#ffffff;}
    .st-key-alert_chat_panel .bubble-user a {text-decoration:underline;}
    .st-key-alert_chat_panel .bubble-user .messenger-meta {color:#dbeafe;}
    .st-key-alert_chat_panel [data-testid="stChatMessage"]:has(.bubble-user) .messenger-meta {text-align:right;}
    .st-key-alert_chat_panel .messenger-meta {
        margin:5px 3px 0; color:var(--muted); font-size:13px; line-height:1.5;
        overflow-wrap:anywhere;
    }
    .st-key-alert_chat_panel .messenger-event-title {
        color:var(--ink); font-size:14px; font-weight:750; line-height:1.55; margin:0 0 7px;
    }
    .st-key-alert_chat_panel .messenger-event-detail {
        color:var(--ink); font-size:14px; line-height:1.65; margin:7px 0 0;
        overflow-wrap:anywhere;
    }
    .st-key-alert_chat_panel .messenger-badge {
        display:inline-flex; align-items:center; max-width:100%; vertical-align:middle;
        padding:3px 7px; margin:3px 4px 3px 0; border-radius:6px;
        background:var(--surface-raised); color:var(--muted); font-size:13px;
        font-weight:600; line-height:1.5; overflow-wrap:anywhere;
    }
    .st-key-alert_chat_panel .badge-critical {background:var(--critical-soft); color:var(--critical);}
    .st-key-alert_chat_panel .badge-warning {background:var(--warning-soft); color:var(--warning);}
    .st-key-alert_chat_panel .badge-source {font-weight:500;}
    .st-key-alert_chat_panel .badge-new {background:var(--soft); color:var(--accent);}
    .st-key-alert_chat_panel .messenger-empty {
        display:flex; flex-direction:column; align-items:center; justify-content:center;
        min-height:190px; padding:24px 14px; color:var(--muted); text-align:center;
        font-size:14px; line-height:1.7;
    }
    .st-key-alert_chat_panel .messenger-empty strong {display:block; margin-bottom:7px; color:var(--ink); font-size:15px;}
    .st-key-alert_chat_panel .messenger-divider {
        display:flex; align-items:center; gap:10px; margin:9px 0; color:var(--muted);
        font-size:13px; line-height:1.5; text-align:center;
    }
    .st-key-alert_chat_panel .messenger-divider::before,
    .st-key-alert_chat_panel .messenger-divider::after {content:""; flex:1; min-width:12px; height:1px; background:var(--line);}
    .st-key-alert_chat_panel .st-key-alert_chat_question [data-testid="stChatInput"],
    .st-key-alert_chat_panel .st-key-alert_chat_question[data-testid="stChatInput"] {
        min-height:48px; background:var(--surface-raised); border:1px solid var(--line); border-radius:24px;
    }
    .st-key-alert_chat_panel .st-key-alert_chat_question [data-testid="stChatInput"]:focus-within,
    .st-key-alert_chat_panel .st-key-alert_chat_question[data-testid="stChatInput"]:focus-within {
        border-color:var(--accent); box-shadow:0 0 0 2px var(--soft);
    }
    .st-key-alert_chat_panel .st-key-alert_chat_question textarea {
        color:var(--ink); background:transparent; font-size:14px; line-height:1.6;
    }
    .st-key-alert_chat_panel [data-testid="stChatInputSubmitButton"] {
        display:grid; place-items:center; min-width:44px; min-height:44px;
        border-radius:50%; color:var(--accent);
    }
    .st-key-alert_chat_panel .st-key-alert_chat_prompts [data-testid="stButton"] button {
        min-height:44px; border-radius:20px; padding:8px 12px; font-size:13px;
        font-weight:600; background:var(--surface); border-color:var(--line); color:var(--accent);
    }
    .st-key-alert_chat_panel .st-key-alert_chat_prompts [data-testid="stButton"] button:hover {
        background:var(--soft); border-color:var(--accent);
    }
    .st-key-alert_chat_panel .st-key-alert_chat_prompts [data-testid="stHorizontalBlock"] {display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:7px;}
    .st-key-alert_chat_panel .st-key-alert_chat_context_row [data-testid="stHorizontalBlock"] {display:grid; grid-template-columns:minmax(0, 3fr) minmax(75px, 1fr); gap:8px;}
    .st-key-alert_chat_panel :is(.st-key-alert_chat_prompts, .st-key-alert_chat_context_row) [data-testid="stColumn"] {width:auto !important; min-width:0 !important; flex:unset !important;}
    .st-key-alert_chat_panel .st-key-alert_chat_jump_latest button {min-height:44px; border-radius:12px; color:var(--accent); background:var(--soft);}
    .st-key-alert_chat_panel .st-key-alert_chat_prompts [data-testid="stMarkdownContainer"] p {font-size:13px; line-height:1.5;}
    .st-key-alert_chat_panel [data-testid="stExpander"] summary {min-height:44px;}

    .st-key-monitor_screen {margin-bottom:1.1rem;}
    .st-key-monitor_screen [role="radiogroup"] {
        display:flex; gap:5px; padding:5px; background:var(--surface);
        border:1px solid var(--line); border-radius:12px; box-shadow:var(--card-shadow);
    }
    .st-key-monitor_screen [role="radiogroup"] label {
        flex:1 1 0; display:flex; align-items:center; justify-content:center;
        min-height:46px; padding:8px 14px; margin:0; border:1px solid transparent;
        border-radius:8px; color:var(--muted); font-weight:650; transition:background-color .15s;
    }
    .st-key-monitor_screen [role="radiogroup"] label:hover {background:var(--surface-raised); color:var(--ink);}
    .st-key-monitor_screen [role="radiogroup"] label:has(input:checked),
    .st-key-monitor_screen [role="radiogroup"] label[data-selected="true"] {
        background:var(--soft); color:var(--accent); border-color:var(--line);
    }
    .st-key-monitor_screen [role="radiogroup"] label:has(input:checked) p {color:var(--accent); font-weight:700;}
    .st-key-monitor_screen [role="radiogroup"] label:has(input:focus-visible),
    .st-key-interface_mode [role="radiogroup"] label:has(input:focus-visible) {outline:3px solid var(--accent); outline-offset:2px;}
    .st-key-interface_mode [role="radiogroup"] {display:flex; flex-direction:column; gap:6px;}
    .st-key-interface_mode [role="radiogroup"] label {min-height:44px; padding:10px 12px; margin:0; border-radius:9px; border:1px solid transparent;}
    .st-key-interface_mode [role="radiogroup"] label:has(input:checked),
    .st-key-interface_mode [role="radiogroup"] label[data-selected="true"] {background:var(--soft); border-color:var(--line); color:var(--accent);}
    .st-key-interface_mode [role="radiogroup"] label:has(input:checked) p {font-weight:700; color:var(--accent);}

    .brand {font-size:1.1rem; font-weight:800; letter-spacing:.025em; color:var(--accent); margin-bottom:.25rem;}
    .brand-lockup {display:flex; align-items:center; gap:11px; margin:.25rem 0 1.7rem;}
    .brand-lockup .brand {font-size:1rem; margin:0; letter-spacing:.04em;}
    .brand-mark {display:grid; place-items:center; flex:0 0 40px; width:40px; height:40px; background:var(--accent); color:var(--surface); font-size:.88rem; font-weight:800; border-radius:11px;}
    .brand-subtitle {display:block; font-size:.7rem; line-height:1.5; margin-top:.25rem; color:var(--muted);}
    .eyebrow {color:var(--accent); font-size:.71rem; font-weight:750; letter-spacing:.11em; margin-bottom:.6rem;}
    .hero {padding:.35rem 0 1.4rem;}
    .hero h1 {font-size:clamp(1.7rem, 2.8vw, 2.35rem); font-weight:750; line-height:1.2; margin:0 0 .65rem; color:var(--ink);}
    .hero p {color:var(--muted); margin:0; max-width:780px; line-height:1.65;}
    .steps {display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin:.25rem 0 1.6rem;}
    .step {background:var(--surface); border:1px solid var(--line); border-radius:11px; padding:14px 16px; color:var(--ink); font-size:.88rem;}
    .step b {display:inline-grid; place-items:center; width:27px; height:27px; background:var(--soft); color:var(--accent); border-radius:8px; margin-right:9px;}
    .empty-state {padding:32px 24px; text-align:center; background:var(--surface); border:1px dashed var(--line); border-radius:14px; margin-top:12px;}
    .empty-state strong {display:block; font-size:1.05rem; color:var(--ink); margin-bottom:.55rem;}
    .empty-state p {color:var(--muted); margin:0; font-size:.9rem; line-height:1.65;}

    @media(max-width:1100px) {
        .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {grid-template-columns:repeat(2, minmax(0, 1fr));}
        .st-key-monitor_metrics [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {grid-column:1 / -1;}
        .workspace-header {align-items:flex-start;}
        .header-tags {max-width:250px;}
    }
    @media(min-width:1800px) {
        .st-key-monitor_dashboard .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {grid-template-columns:repeat(5, minmax(0, 1fr));}
    }
    @media(max-width:1200px) {
        .st-key-monitor_dashboard > [data-testid="stHorizontalBlock"],
        .st-key-monitor_dashboard > div > [data-testid="stHorizontalBlock"] {display:flex; flex-direction:column; gap:1.5rem;}
        .st-key-monitor_dashboard > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
        .st-key-monitor_dashboard > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {width:100% !important; min-width:0 !important; flex:unset !important;}
        .st-key-monitor_dashboard .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {grid-template-columns:repeat(2, minmax(0, 1fr));}
        .st-key-monitor_dashboard .st-key-monitor_metrics [data-testid="stColumn"]:last-child {grid-column:1 / -1;}
    }
    @media(max-width:950px) {
        .st-key-monitor_control_columns > [data-testid="stHorizontalBlock"],
        .st-key-monitor_control_columns > div > [data-testid="stHorizontalBlock"] {display:grid; grid-template-columns:minmax(0, 1fr); gap:18px;}
        .st-key-monitor_control_columns > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
        .st-key-monitor_control_columns > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {width:100% !important; min-width:0 !important;}
    }
    @media(max-width:700px) {
        .block-container {padding:2.7rem 1rem 2rem;}
        .workspace-header {display:block; padding-bottom:1rem;}
        .workspace-header h1 {font-size:1.65rem;}
        .header-tags {justify-content:flex-start; max-width:none; margin-top:.85rem;}
        .workspace-subtitle {font-size:.9rem;}
        .health-grid {grid-template-columns:repeat(2, minmax(0, 1fr)); gap:9px;}
        .health-cell {padding:13px 15px;}
        .guide-grid, .steps, .incident-counts {grid-template-columns:1fr; gap:10px;}
        .section-heading {align-items:flex-start; flex-direction:column; gap:.35rem;}
        .st-key-monitor_screen [role="radiogroup"] {flex-direction:row; align-items:stretch;}
        .st-key-monitor_screen [role="radiogroup"] label {justify-content:center; min-height:62px; padding:7px 6px; text-align:center;}
        .st-key-monitor_screen [role="radiogroup"] label p {font-size:.8rem; line-height:1.45; white-space:normal;}
        .alert-summary {padding:13px 14px;}
        [data-testid="stMetric"] {padding:15px; min-height:118px;}
        [data-testid="stForm"] {padding:13px;}
        .source-notice {align-items:flex-start; padding:11px 12px;}
        .source-notice .status-dot {margin-top:.45rem;}
        .source-notice > span:last-child {flex-basis:100%;}
        .st-key-monitor_metrics [data-testid="stColumn"]:last-child .metric-context {padding-bottom:14px;}
        [data-testid="stDialog"] [role="dialog"] {max-width:calc(100vw - 1rem); padding:1rem;}
        [class*="st-key-admin_assistant_chat_history"] {max-height:45dvh;}
        [data-testid="stPlotlyChart"] {padding:3px 0;}
        .st-key-alert_chat_panel .messenger-header {gap:10px; padding:12px;}
        .st-key-alert_chat_panel .messenger-avatar {flex-basis:36px; width:36px; height:36px; border-radius:12px;}
        .st-key-alert_chat_panel .messenger-title,
        .st-key-alert_chat_panel .messenger-header h3,
        .st-key-alert_chat_panel .messenger-header strong {font-size:16px;}
        .st-key-alert_chat_panel .messenger-action {font-size:13px;}
        .st-key-alert_chat_panel .st-key-alert_chat_timeline {max-height:60dvh; padding:10px 8px;}
        .st-key-alert_chat_panel [data-testid="stChatMessage"] {gap:7px;}
        .st-key-alert_chat_panel [data-testid="stChatMessageContent"] {max-width:calc(100% - 35px);}
        .st-key-alert_chat_panel .messenger-bubble {padding:10px 12px; font-size:14px;}
        .st-key-alert_chat_panel .st-key-alert_chat_prompts [data-testid="stHorizontalBlock"] {gap:7px;}
    }
    @media(max-width:460px) {
        [data-testid="stMetricValue"] {font-size:1.5rem;}
        .metric-context {padding-left:12px; padding-right:12px;}
        .st-key-monitor_metrics [data-testid="stMetric"] {padding-left:12px; padding-right:12px;}
        .health-cell {padding:12px;}
        .health-value {font-size:.92rem;}
        .health-meta {font-size:.78rem;}
    }
    @media(max-width:360px) {
        .health-grid, .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {grid-template-columns:minmax(0, 1fr);}
        .st-key-monitor_dashboard .health-grid, .st-key-monitor_dashboard .st-key-monitor_metrics [data-testid="stHorizontalBlock"] {grid-template-columns:minmax(0, 1fr);}
        .st-key-monitor_screen [role="radiogroup"] {flex-direction:column;}
        .st-key-monitor_screen [role="radiogroup"] label {justify-content:flex-start; min-height:44px; text-align:left;}
    }
    @media(prefers-reduced-motion:reduce) {
        .stApp button, .st-key-monitor_screen label {transition:none !important;}
    }
    __DARK_ALERTS__
    </style>
    """
    palette["dark_alerts"] = """
    [data-testid="stAlert"] > div {
        background:var(--surface-raised) !important; color:var(--ink) !important;
        border-color:var(--line) !important;
    }
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {color:var(--ink) !important;}
    """ if dark else ""
    for key, value in palette.items():
        css = css.replace(f"__{key.upper()}__", value)
    st.markdown(css, unsafe_allow_html=True)
