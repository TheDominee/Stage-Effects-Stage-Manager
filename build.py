import re
import shutil
import os

def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()

# Stage Effects brand now ships as vector SVG logos in two color variants:
# white (for dark backgrounds — dark UI theme, night displays) and black
# (for light backgrounds — light/day UI theme, and printed pages, which are
# always on white paper regardless of what theme was active on screen).
logo_se_dark_bg = read('logo_se_white_b64.txt').strip()   # white logo, sits on a dark plate
logo_se_light_bg = read('logo_se_black_b64.txt').strip()  # black logo, sits on a light plate
# Spaan only has the one logo file (no separate white/black variants), so it
# is used for both slots — no visual change there, just keeps templating uniform.
logo_spaan = read('spaan_logo_new_b64.txt').strip()

def build_sm(template, logo_dark_b64, logo_light_b64, logo_mime, enable_doors, crew_url, brand_title,
             local_crew_file, local_viewer_file, out, brand_footer_name=None):
    src = template
    src = src.replace('{{LOGO_B64_DARK}}', logo_dark_b64)
    src = src.replace('{{LOGO_B64_LIGHT}}', logo_light_b64)
    src = src.replace('{{LOGO_MIME}}', logo_mime)
    src = src.replace('{{ENABLE_DOORS_COUNTDOWN}}', enable_doors)
    src = src.replace('{{DEFAULT_CREW_URL}}', crew_url)
    src = src.replace('{{BRAND_TITLE}}', brand_title)
    # The "built for ___" footer credit line needs its own, separate value:
    # BRAND_TITLE is the short name used all over the UI ("Stage Effects" /
    # "Spaan"), but this one spot has always carried Stage Effects' full
    # legal name too ("Stage Effects Group (Pty) Ltd") -- falling back to
    # brand_title keeps that exact wording for Stage Effects while giving
    # Spaan's build its own name here instead of Stage Effects' (this line
    # used to be hardcoded and leaked "Stage Effects Group (Pty) Ltd" into
    # the Spaan build's footer -- fixed 2026-09-21).
    src = src.replace('{{BRAND_FOOTER_NAME}}', brand_footer_name or brand_title)
    # Which Crew/Viewer HTML filenames the Local Broadcast app should be
    # asked for -- brand-specific, so a Spaan show's local broadcast hands
    # out Spaan-branded links/QR codes, not Stage Effects' by mistake.
    src = src.replace('{{LOCAL_CREW_FILE}}', local_crew_file)
    src = src.replace('{{LOCAL_VIEWER_FILE}}', local_viewer_file)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(src)

def build_viewer(template, logo_dark_b64, logo_light_b64, logo_mime, enable_crew_chat, brand_title, out):
    src = template
    src = src.replace('{{LOGO_B64_DARK}}', logo_dark_b64)
    src = src.replace('{{LOGO_B64_LIGHT}}', logo_light_b64)
    src = src.replace('{{LOGO_MIME}}', logo_mime)
    src = src.replace('{{ENABLE_CREW_CHAT}}', enable_crew_chat)
    src = src.replace('{{BRAND_TITLE}}', brand_title)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(src)

sm_template = read('template.html')
viewer_template = read('viewer_template.html')

build_sm(sm_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'true',
         'https://thedominee.github.io/Stage-Effects-Stage-Manager/Stage_Effects_Crew.html',
         'Stage Effects',
         'Stage_Effects_Crew.html', 'Stage_Effects_Viewer.html',
         'Stage_Effects_Stage_Manager.html',
         brand_footer_name='Stage Effects Group (Pty) Ltd')
# Spaan is its own act with its own crew -- they get their own branded Crew
# Talk page (Spaan_Crew.html, Spaan logo) rather than sharing Stage Effects'
# page, and Spaan's control panel defaults its Crew URL to that page.
build_sm(sm_template, logo_spaan, logo_spaan, 'image/png', 'false',
         'https://thedominee.github.io/Stage-Effects-Stage-Manager/Spaan_Crew.html',
         'Spaan',
         'Spaan_Crew.html', 'Spaan_Viewer.html',
         'Spaan_Stage_Manager_Countdown.html')

build_viewer(viewer_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'false', 'Stage Effects', 'viewer.html')
build_viewer(viewer_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'false', 'Stage Effects', 'Stage_Effects_Viewer.html')
build_viewer(viewer_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'false', 'Stage Effects', 'index.html')
build_viewer(viewer_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'true', 'Stage Effects', 'Stage_Effects_Crew.html')
# Spaan's Crew/Viewer pages are the ones that actually go out live over a
# broadcast link (to crew phones, to the audience) -- Stage Effects Group is
# always the sole IP owner and Spaan piggybacks on that property, so these
# pages always carry the Stage Effects LOGO regardless of brand (per Erik,
# 2026-09-21). "Spaan" still appears as the page's own name/title text --
# only the logo image itself is fixed to Stage Effects. Spaan's own distinct
# branding is reserved for the Extended Display output on the hard-wired
# local monitor (see template.html's presenter overlay), never broadcast.
build_viewer(viewer_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'true', 'Spaan', 'Spaan_Crew.html')
build_viewer(viewer_template, logo_se_dark_bg, logo_se_light_bg, 'image/svg+xml', 'false', 'Spaan', 'Spaan_Viewer.html')

# The one-click Local Broadcast app bundles its own copies of the Crew/
# Viewer pages AND both Stage Manager control panels (it serves them
# straight from its own folder, offline) -- keep those copies fresh on
# every build so a theme/feature change here doesn't quietly drift out of
# sync with what the local-network app actually hands out. Bundling the
# control panels themselves (not just Crew/Viewer) is what lets Erik open
# Stage Manager FROM the app over plain http instead of the usual https
# link -- the fix for local broadcast being blocked in Safari/on some
# networks (see template.html's localWriteBase() for the full story).
LOCAL_BROADCAST_DIR = 'local-broadcast-server'
if os.path.isdir(LOCAL_BROADCAST_DIR):
    for fname in ('Stage_Effects_Crew.html', 'Stage_Effects_Viewer.html',
                  'Spaan_Crew.html', 'Spaan_Viewer.html',
                  'Stage_Effects_Stage_Manager.html', 'Spaan_Stage_Manager_Countdown.html'):
        shutil.copyfile(fname, os.path.join(LOCAL_BROADCAST_DIR, fname))

print("Build complete")
