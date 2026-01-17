import json
import time
import os

TIMESTAMP = int(time.time())
OUTPUT_DIR = r"c:\Users\User\Desktop\novabot\_bmad-output\excalidraw-diagrams"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"wireframe-dashboard.excalidraw")

# Dark UI Theme
COLORS = {
    "bg": "#1e1e1e",
    "container": "#2d2d2d",
    "border": "#4caf50",  # Green accent for Novabot
    "text": "#e0e0e0",
    "accent": "#2196f3",   # Blue
    "danger": "#f44336",
    "success": "#4caf50"
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
        "strokeColor": COLORS["border"],
        "backgroundColor": COLORS["container"],
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
            "fontSize": kwargs.get("fontSize", 20),
            "fontFamily": 1,
            "textAlign": kwargs.get("textAlign", "left"),
            "verticalAlign": kwargs.get("verticalAlign", "top"),
            "baseline": 18,
            "containerId": kwargs.get("containerId", None),
            "strokeColor": COLORS["text"]
        })
        # Approximate width calculation if not explicit
        if "width" not in kwargs:
             element["width"] = len(element["text"]) * element["fontSize"] * 0.6

    element.update(kwargs)
    ELEMENTS.append(element)
    return element

def add_rect(x, y, w, h, color=COLORS["container"], stroke=COLORS["border"], label=None, **kwargs):
    rect_id = str(time.time_ns()) + "_rect"
    grp_id = str(time.time_ns()) + "_grp"
    
    rect_kwargs = kwargs.copy()
    rect_kwargs["backgroundColor"] = color
    rect_kwargs["strokeColor"] = stroke
    rect_kwargs["id"] = rect_id
    
    if label:
        rect_kwargs["groupIds"] = [grp_id]
        
    rect = create_element("rectangle", x, y, w, h, **rect_kwargs)
    
    if label:
        text_id = str(time.time_ns()) + "_text"
        create_element("text", x + 10, y + (h/2) - 10, w-20, 20, 
                       text=label, 
                       textAlign="center", 
                       verticalAlign="middle",
                       containerId=rect_id,
                       groupIds=[grp_id],
                       id=text_id,
                       fontSize=16)
        rect["boundElements"] = [{"type": "text", "id": text_id}]
        
    return rect

# --- BUILD WIREFRAME ---

# 1. Main Container
main_w, main_h = 1200, 900
add_rect(0, 0, main_w, main_h, COLORS["bg"], "#000000", strokeWidth=2)

# 2. Header
header_h = 80
add_rect(0, 0, main_w, header_h, COLORS["container"], COLORS["border"], label="")
create_element("text", 20, 25, 200, 30, text="NOVABOT DASHBOARD", fontSize=24, strokeColor=COLORS["accent"])

# Status Pill
add_rect(main_w - 300, 20, 120, 40, COLORS["success"], COLORS["success"], label="RUNNING", roundness={"type": 3})

# Wallet Info
create_element("text", main_w - 150, 30, 200, 20, text="Balance: $12,450", fontSize=16)

# 3. Sidebar (Right)
sidebar_w = 300
sidebar_x = main_w - sidebar_w
add_rect(sidebar_x, header_h, sidebar_w, main_h - header_h, "#252525", COLORS["border"])

# Sidebar Content
# Controls
create_element("text", sidebar_x + 20, header_h + 20, 200, 20, text="CONTROLS", fontSize=18, strokeColor="#888")
add_rect(sidebar_x + 20, header_h + 60, 110, 50, COLORS["success"], COLORS["success"], label="START", roundness={"type": 3})
add_rect(sidebar_x + 150, header_h + 60, 110, 50, COLORS["danger"], COLORS["danger"], label="STOP", roundness={"type": 3})

# Strategy Selector
create_element("text", sidebar_x + 20, header_h + 150, 200, 20, text="ACTIVE STRATEGY", fontSize=18, strokeColor="#888")
add_rect(sidebar_x + 20, header_h + 190, 250, 40, COLORS["container"], "#555", label="Elastic Nibbler ▼", roundness={"type": 2})

# Market Regime
create_element("text", sidebar_x + 20, header_h + 270, 200, 20, text="MARKET REGIME", fontSize=18, strokeColor="#888")
add_rect(sidebar_x + 20, header_h + 310, 250, 80, "#333", "#444", label="TRENDING (UP)\nADX: 42.5 (Strong)", strokeStyle="dashed")

# Logs
create_element("text", sidebar_x + 20, header_h + 430, 200, 20, text="LIVE LOGS", fontSize=18, strokeColor="#888")
add_rect(sidebar_x + 20, header_h + 460, 250, 320, "#111", "#333")
create_element("text", sidebar_x + 30, header_h + 470, 230, 300, 
               text="[12:01] Scan complete\n[12:02] Signal detected: BTC\n[12:02] Order placed #4492\n[12:05] TP Updated", 
               fontSize=12, strokeColor="#aaa", fontFamily=3)

# 4. Main Content Area
main_content_w = main_w - sidebar_w
main_content_h = main_h - header_h

# Chart Area
chart_h = 500
add_rect(20, header_h + 20, main_content_w - 40, chart_h, "#1a1a1a", "#333")
create_element("text", 40, header_h + 40, 200, 20, text="BTC/USDT - 15m", fontSize=20, strokeColor="#bbb")
# Fake Chart Lines
create_element("line", 50, header_h + 400, 800, 200, 
               points=[[0, 0], [100, -50], [200, -30], [300, -100], [400, -80], [500, -150], [600, -120], [700, -200]],
               strokeColor=COLORS["success"], strokeWidth=2)

# Positions Table
table_y = header_h + chart_h + 40
create_element("text", 20, table_y - 30, 200, 20, text="ACTIVE POSITIONS", fontSize=18, strokeColor="#888")
add_rect(20, table_y, main_content_w - 40, 200, COLORS["container"], "#333")

# Table Header
headers = ["Symbol", "Side", "Size", "Entry", "Mark", "PnL", "Action"]
col_w = (main_content_w - 60) / 7
for i, h in enumerate(headers):
    create_element("text", 40 + (i * col_w), table_y + 15, 100, 20, text=h, fontSize=14, strokeColor="#bbb")

# Table Row 1
row_y = table_y + 50
data = ["BTC/USDT", "LONG", "0.5 BTC", "98,240", "98,450", "+$105 (0.5%)", "[CLOSE]"]
for i, d in enumerate(data):
    color = COLORS["success"] if "+" in d else COLORS["text"]
    create_element("text", 40 + (i * col_w), row_y, 100, 20, text=d, fontSize=14, strokeColor=color)


# --- SAVE ---
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

output_data = {
    "type": "excalidraw",
    "version": 2,
    "source": "novabot-agent",
    "elements": ELEMENTS,
    "appState": {
        "viewBackgroundColor": COLORS["bg"],
        "gridSize": 20
    }
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Wireframe saved to {OUTPUT_FILE}")
print(f"Total elements: {len(ELEMENTS)}")
