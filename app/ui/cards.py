"""
Card-based UI components for a modern dashboard
Inspired by BoxProof design with glassmorphism and hover effects
"""
import streamlit as st

def render_stat_card(icon, label, value, delta=None, color="blue"):
    """
    Render a beautiful stat card with icon, label, and value
    
    Args:
        icon: Emoji or icon
        label: Card label
        value: Main value to display
        delta: Optional delta/subtitle
        color: Color theme (blue, green, orange, purple, red)
    """
    color_map = {
        "blue": "#3b82f6",
        "green": "#22c55e",
        "orange": "#f97316",
        "purple": "#a855f7",
        "red": "#ef4444",
        "cyan": "#06b6d4",
        "yellow": "#eab308"
    }
    
    accent_color = color_map.get(color, color_map["blue"])
    
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(30, 41, 59, 0.7));
        backdrop-filter: blur(10px);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 1rem;
        padding: 1.25rem;
        transition: all 0.3s ease;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    " onmouseover="this.style.transform='translateY(-4px)'; this.style.borderColor='{accent_color}'; this.style.boxShadow='0 10px 30px rgba(59, 130, 246, 0.3)';" 
       onmouseout="this.style.transform='translateY(0)'; this.style.borderColor='rgba(59, 130, 246, 0.2)'; this.style.boxShadow='none';">
        
        <!-- Gradient overlay -->
        <div style="
            position: absolute;
            top: 0;
            right: 0;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, {accent_color}33 0%, transparent 70%);
            pointer-events: none;
        "></div>
        
        <!-- Icon -->
        <div style="
            font-size: 2rem;
            margin-bottom: 0.5rem;
            opacity: 0.9;
        ">{icon}</div>
        
        <!-- Label -->
        <div style="
            color: #94a3b8;
            font-size: 0.75rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        ">{label}</div>
        
        <!-- Value -->
        <div style="
            color: #f8fafc;
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        ">{value}</div>
        
        <!-- Delta -->
        {"" if not delta else f'''
        <div style="
            color: #cbd5e1;
            font-size: 0.875rem;
            font-weight: 500;
        ">{delta}</div>
        '''}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

def render_info_card(title, content, icon="📊", color="blue"):
    """
    Render an information card with title and content
    """
    color_map = {
        "blue": "#3b82f6",
        "green": "#22c55e",
        "orange": "#f97316",
        "purple": "#a855f7",
        "red": "#ef4444"
    }
    
    accent_color = color_map.get(color, color_map["blue"])
    
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(30, 41, 59, 0.8));
        backdrop-filter: blur(10px);
        border: 1px solid rgba(51, 65, 85, 0.6);
        border-left: 4px solid {accent_color};
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    " onmouseover="this.style.transform='translateX(4px)'; this.style.borderLeftWidth='6px';" 
       onmouseout="this.style.transform='translateX(0)'; this.style.borderLeftWidth='4px';">
        
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
            <span style="font-size: 1.5rem;">{icon}</span>
            <h4 style="
                color: #f8fafc;
                font-size: 1.125rem;
                font-weight: 600;
                margin: 0;
            ">{title}</h4>
        </div>
        
        <div style="
            color: #cbd5e1;
            font-size: 0.875rem;
            line-height: 1.6;
        ">{content}</div>
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

def render_strategy_card(strategy_name, status, conditions, color="blue"):
    """
    Render a strategy monitoring card
    """
    color_map = {
        "blue": "#3b82f6",
        "green": "#22c55e",
        "orange": "#f97316",
        "purple": "#a855f7"
    }
    
    accent_color = color_map.get(color, color_map["blue"])
    
    # Build conditions HTML
    conditions_html = ""
    for cond in conditions:
        check = "✅" if cond.get("met", False) else "❌"
        conditions_html += f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
        ">
            <span>{check}</span>
            <div style="flex: 1;">
                <div style="color: #f8fafc; font-size: 0.875rem; font-weight: 500;">{cond.get('name', '')}</div>
                <div style="color: #94a3b8; font-size: 0.75rem;">{cond.get('value', '')}</div>
            </div>
        </div>
        """
    
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(30, 41, 59, 0.8));
        backdrop-filter: blur(10px);
        border: 1px solid rgba(51, 65, 85, 0.6);
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    " onmouseover="this.style.borderColor='{accent_color}'; this.style.boxShadow='0 8px 24px rgba(59, 130, 246, 0.2)';" 
       onmouseout="this.style.borderColor='rgba(51, 65, 85, 0.6)'; this.style.boxShadow='none';">
        
        <!-- Header -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid rgba(51, 65, 85, 0.6);
        ">
            <h4 style="
                color: #f8fafc;
                font-size: 1rem;
                font-weight: 600;
                margin: 0;
            ">{strategy_name}</h4>
            
            <span style="
                background: {accent_color}33;
                color: {accent_color};
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 500;
            ">{status}</span>
        </div>
        
        <!-- Conditions -->
        {conditions_html}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)

def render_header_card(title, subtitle=None, badge=None):
    """
    Render a header card with title, optional subtitle and badge
    """
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(30, 41, 59, 0.7));
        backdrop-filter: blur(10px);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 1rem;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <div>
            <h1 style="
                color: #f8fafc;
                font-size: 2rem;
                font-weight: 700;
                margin: 0 0 0.5rem 0;
                background: linear-gradient(135deg, #3b82f6, #60a5fa);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            ">{title}</h1>
            {"" if not subtitle else f'''
            <p style="
                color: #94a3b8;
                font-size: 0.875rem;
                margin: 0;
            ">{subtitle}</p>
            '''}
        </div>
        
        {"" if not badge else f'''
        <div style="
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
            padding: 0.5rem 1.5rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        ">{badge}</div>
        '''}
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)
