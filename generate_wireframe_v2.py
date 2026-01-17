import json
import time
import os

TIMESTAMP = int(time.time())
OUTPUT_DIR = r"c:\Users\User\Desktop\novabot\_bmad-output\excalidraw-diagrams"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"wireframe-dashboard-v2.excalidraw")

# Refined Dark Theme based on Image
COLORS = {
    "bg": "#0a0a0a",        # Very dark background
    "container": "#141414", # Slightly lighter for cards
    "border": "#333333",
    "text": "#e0e0e0",
    "muted": "#888888",
    "accent": "#00ff9d",    # Neon Green
    "accent_blue": "#2962ff",
    "danger": "#ff3d60",
    "success": "#00ff9d"
}

ELEMENTS = []

def create_element(type, x, y, width, height, **kwargs):
    element = {
        "type": type,
        "version": 1,
        "versionNonce": 0,
        "isDeleted": False,
        "id": kwargs.get("id", str(time.time_ns()) + str(len(ELEMENTS))),
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "angle": 0,
        "x": x,
        "y": y,
        "strokeColor": kwargs.get("strokeColor", COLORS["border"]),
        "backgroundColor": kwargs.get("backgroundColor", "transparent"),
        "width": width,
        "height": height,
        "seed": int(time.time() * 1000),
        "groupIds": kwargs.get("groupIds", []),
        "roundness": kwargs.get("roundness", None),
        "boundElements": kwargs.get("boundElements", []),
        "updated": int(time.time() * 1000),
        "link": None,
        "locked": False,
    }
    
    if type == "text":
        element.update({
            "text": kwargs.get("text", ""),
            "fontSize": kwargs.get("fontSize", 16),
            "fontFamily": 1,
            "textAlign": kwargs.get("textAlign", "left"),
            "verticalAlign": kwargs.get("verticalAlign", "top"),
            "baseline": 18,
            "containerId": kwargs.get("containerId", None),
            "strokeColor": kwargs.get("strokeColor", COLORS["text"])
        })
        # Approximate width calculation if not explicit
        if "width" not in kwargs:
             element["width"] = len(element["text"]) * element["fontSize"] * 0.6

    element.update(kwargs)
    ELEMENTS.append(element)
    return element

def add_rect(x, y, w, h, color=COLORS["container"], stroke=COLORS["border"], label=None, labelSize=16, labelColor=COLORS["text"], **kwargs):
    rect_id = str(time.time_ns()) + "_rect" + str(len(ELEMENTS))
    grp_id = str(time.time_ns()) + "_grp" + str(len(ELEMENTS))
    
    rect_kwargs = kwargs.copy()
    rect_kwargs["backgroundColor"] = color
    rect_kwargs["strokeColor"] = stroke
    rect_kwargs["id"] = rect_id
    
    if label:
        rect_kwargs["groupIds"] = [grp_id]
        
    rect = create_element("rectangle", x, y, w, h, **rect_kwargs)
    
    if label:
        text_id = str(time.time_ns()) + "_text" + str(len(ELEMENTS))
        create_element("text", x + 10, y + (h/2) - 10, w-20, 20, 
                       text=label, 
                       textAlign="center", 
                       verticalAlign="middle",
                       containerId=rect_id,
                       groupIds=[grp_id],
                       id=text_id,
                       fontSize=labelSize,
                       strokeColor=labelColor)
        rect["boundElements"] = [{"type": "text", "id": text_id}]
        
    return rect

# --- BUILD WIREFRAME V2 ---

main_w, main_h = 1400, 900
add_rect(0, 0, main_w, main_h, COLORS["bg"], "#000000", strokeWidth=0)

# 1. Header Area
header_h = 60
create_element("text", 20, 20, 200, 30, text="⚡ HyperLiquid AI", fontSize=20, strokeColor=COLORS["text"])
create_element("text", 200, 25, 100, 20, text="NOVA BOT • v2.0", fontSize=12, strokeColor=COLORS["muted"])

# Right Header Info
add_rect(main_w - 120, 15, 100, 30, "#003300", COLORS["success"], label="● ONLINE", labelSize=12, labelColor=COLORS["success"], roundness={"type": 3})
create_element("text", main_w - 300, 15, 150, 40, text="Goblin • 1 Tiers Unlocked\n$53.08 to Mercenary", fontSize=12, textAlign="right", strokeColor=COLORS["muted"])


# 2. Navigation Tabs
tabs_y = 70
tabs = ["Price Chart", "Strategies", "Signals", "Scanner", "AI Analysis", "System Logs", "Config", "Dev Ops"]
tab_x = 20
for i, tab in enumerate(tabs):
    color = COLORS["accent_blue"] if i == 0 else COLORS["muted"]
    stroke = COLORS["accent_blue"] if i == 0 else "transparent"
    
    create_element("text", tab_x, tabs_y, 100, 20, text=tab, fontSize=16, strokeColor=color)
    if i == 0:
        create_element("line", tab_x, tabs_y + 25, 100, 0, points=[[0,0], [80, 0]], strokeColor=COLORS["accent_blue"], strokeWidth=2)
    tab_x += 140

# 3. Main Layout Grid
content_y = 120
right_col_w = 400
left_col_w = main_w - right_col_w - 60 # 20px padding left, 20px gap, 20px padding right

# --- LEFT COLUMN (Chart & sentiment) ---

# Chart Container
chart_h = 500
add_rect(20, content_y, left_col_w, chart_h, COLORS["container"], COLORS["border"], roundness={"type": 3})

# Chart Header overlay
add_rect(40, content_y + 20, 100, 30, "#333", "transparent", label="DOGE 15m", labelSize=14, roundness={"type": 2})

# Chart Content (Simulation)
create_element("line", 40, content_y + 400, left_col_w - 40, 200, 
               points=[[0, 0], [100, -50], [200, -30], [300, -150], [400, -80], [500, -200], [600, -180], [700, -100], [800, -50]],
               strokeColor=COLORS["success"], strokeWidth=1)
# EMAs
create_element("line", 40, content_y + 420, left_col_w - 40, 200, 
               points=[[0, 0], [200, -60], [400, -100], [600, -120], [800, -80]],
               strokeColor=COLORS["accent_blue"], strokeWidth=1)
create_element("line", 40, content_y + 450, left_col_w - 40, 200, 
               points=[[0, 0], [200, -40], [400, -60], [600, -80], [800, -60]],
               strokeColor="#9c27b0", strokeWidth=1)

# --- Bottom Left Info Panel ---
info_y = content_y + chart_h + 20
info_h = 180
# Symbol Card
add_rect(20, info_y, 250, info_h, COLORS["container"], COLORS["border"], roundness={"type": 3})
create_element("text", 40, info_y + 20, 100, 30, text="DOGE", fontSize=28, strokeColor=COLORS["text"]) # Symbol
add_rect(40, info_y + 60, 80, 25, "rgba(0,255,157,0.1)", COLORS["success"], label="BULLISH", labelSize=10, labelColor=COLORS["success"], roundness={"type": 2})
add_rect(130, info_y + 60, 80, 25, "rgba(156,39,176,0.1)", "#9c27b0", label="ALIGNED", labelSize=10, labelColor="#9c27b0", roundness={"type": 2})
create_element("text", 40, info_y + 120, 100, 30, text="$0.143", fontSize=32, strokeColor=COLORS["text"]) 

# Timeframe/Signal Cards
tf_start_x = 290
add_rect(tf_start_x, info_y, 400, info_h, COLORS["container"], COLORS["border"], roundness={"type": 3})
# Sparklines Placeholders
for i, tf in enumerate(["15M", "1H", "4H", "1D"]):
    x_pos = tf_start_x + 20 + (i * 95)
    create_element("line", x_pos + 20, info_y + 60, 40, 40, points=[[0,0], [10, 10], [20, -10], [30, 0]], strokeColor=COLORS["danger" if i > 1 else "success"])
    create_element("text", x_pos + 35, info_y + 90, 40, 20, text=tf, fontSize=12, textAlign="center", strokeColor=COLORS["muted"])
    if i < 3: # Dividers
         create_element("line", x_pos + 90, info_y + 40, 0, 100, points=[[0,0], [0, 100]], strokeColor="#333")

# Indicators Card
ind_start_x = 710
add_rect(ind_start_x, info_y, 250, info_h, COLORS["container"], COLORS["border"], roundness={"type": 3})
# Grid of indicators
create_element("text", ind_start_x + 20, info_y + 20, 100, 20, text="RSI\n62", fontSize=14, strokeColor=COLORS["muted"])
create_element("text", ind_start_x + 120, info_y + 20, 100, 20, text="ADX\n36", fontSize=14, strokeColor=COLORS["muted"])
create_element("text", ind_start_x + 20, info_y + 80, 100, 20, text="Vol 24h\n$35.6M", fontSize=14, strokeColor=COLORS["muted"])
create_element("text", ind_start_x + 120, info_y + 80, 100, 20, text="RVol\n0.9x", fontSize=14, strokeColor=COLORS["muted"])

# Ask AI Button
add_rect(ind_start_x + 20, info_y + 125, 210, 40, "#2962ff", "transparent", label="✨ Ask AI", labelColor="#fff", roundness={"type": 3})


# --- RIGHT COLUMN (Position & Insight) ---
right_x = left_col_w + 40

# Active Position Card
pos_h = 220
add_rect(right_x, content_y, right_col_w, pos_h, "#0f1f15", COLORS["success"], roundness={"type": 3}, strokeWidth=2) # Green tint bg

# Header
create_element("text", right_x + 20, content_y + 20, 200, 20, text="BUY DOGE", fontSize=20, strokeColor="#fff")
create_element("text", right_x + 20, content_y + 45, 200, 20, text="MANUAL/ADOPTED", fontSize=10, strokeColor=COLORS["muted"])

# PnL
create_element("text", right_x + 250, content_y + 20, 130, 20, text="CURRENT PNL", fontSize=10, textAlign="right", strokeColor=COLORS["muted"])
create_element("text", right_x + 250, content_y + 35, 130, 30, text="+0.001235", fontSize=24, textAlign="right", strokeColor=COLORS["success"])
create_element("text", right_x + 250, content_y + 65, 130, 20, text="0.87%", fontSize=14, textAlign="right", strokeColor=COLORS["success"])

# Entry/TP
create_element("text", right_x + 20, content_y + 90, 150, 20, text="ENTRY: $0.1417", fontSize=12, strokeColor=COLORS["muted"])
create_element("text", right_x + 260, content_y + 90, 120, 20, text="TP: $0.1444", fontSize=12, strokeColor=COLORS["muted"], textAlign="right")

# Progress Bar
bar_y = content_y + 115
add_rect(right_x + 20, bar_y, right_col_w - 40, 10, "#333", "transparent", roundness={"type": 3})
add_rect(right_x + 20, bar_y, (right_col_w - 40) * 0.46, 10, COLORS["success"], "transparent", roundness={"type": 3})
create_element("text", right_x + 180, bar_y - 5, 50, 20, text="46%", fontSize=10, strokeColor="#fff")

# SL line
create_element("text", right_x + 20, content_y + 135, 100, 20, text="SL: $0.1410", fontSize=12, strokeColor=COLORS["danger"])
create_element("text", right_x + 300, content_y + 135, 80, 20, text="Target Reward", fontSize=10, strokeColor=COLORS["success"], textAlign="right")

# Buttons
btn_y = content_y + 160
add_rect(right_x + 20, btn_y, 170, 40, COLORS["container"], COLORS["border"], label="🔧 FIX", labelColor=COLORS["accent_blue"], roundness={"type": 3})
add_rect(right_x + 210, btn_y, 170, 40, COLORS["container"], COLORS["border"], label="CLOSE →", labelColor="#fff", roundness={"type": 3})


# AI Insight Card
insight_y = content_y + pos_h + 20
insight_h = 300
add_rect(right_x, insight_y, right_col_w, insight_h, COLORS["container"], COLORS["border"], roundness={"type": 3})

# Icon
create_element("text", right_x + 30, insight_y + 30, 30, 30, text="🧠", fontSize=24)

# Text (French Content from image)
ai_text = """La position est actuellement gagnante car le prix
du DOGE est supérieur à la cible de fermeture.
Cependant, la strategie d'investissement est 
une opération dirigée manuellement ce qui rend
les incertitudes considérables.

Il est donc recommandé de garder une position
de medium risk niveau. Il est probablement 
recommandé d'être patient et de ne pas ajuster
la position, car garder le train qui tout 
mouvement est à surveiller, le prix a buté 
contre support intense puis à lagittalèges 
positive."""

create_element("text", right_x + 30, insight_y + 70, 340, 200, 
               text=ai_text, 
               fontSize=14, strokeColor=COLORS["text"])

create_element("text", right_x + 320, insight_y + insight_h - 30, 60, 20, text="🕒 14:25:01", fontSize=12, strokeColor=COLORS["muted"])


# --- SAVE ---
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

output_data = {
    "type": "excalidraw",
    "version": 2,
    "source": "novabot-agent-v2",
    "elements": ELEMENTS,
    "appState": {
        "viewBackgroundColor": COLORS["bg"],
        "gridSize": 20
    }
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Wireframe v2 saved to {OUTPUT_FILE}")
print(f"Total elements: {len(ELEMENTS)}")
