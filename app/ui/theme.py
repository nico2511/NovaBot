"""
BoxProof Theme - Custom CSS for Streamlit
Applies the dark theme with modern components
"""

CUSTOM_CSS = """
<style>
/* Import Inter font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Root variables */
:root {
    /* Primary Colors */
    --color-primary: #3b82f6;
    --color-primary-dark: #2563eb;
    --color-primary-light: #60a5fa;
    
    /* Status Colors */
    --color-success: #22c55e;
    --color-warning: #f97316;
    --color-error: #ef4444;
    --color-info: #3b82f6;
    
    /* Neutral Colors */
    --color-background: #0f172a;
    --color-surface: #1e293b;
    --color-surface-light: #334155;
    --color-border: #475569;
    --color-text-primary: #f8fafc;
    --color-text-secondary: #cbd5e1;
    --color-text-muted: #94a3b8;
    
    /* Spacing */
    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
    --spacing-xl: 2rem;
    
    /* Border Radius */
    --radius-sm: 0.25rem;
    --radius-md: 0.5rem;
    --radius-lg: 1rem;
    --radius-xl: 1.5rem;
    
    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
    --shadow-glow: 0 0 20px rgba(59, 130, 246, 0.3);
}

/* Global font */
* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* Main app background */
.stApp {
    background-color: var(--color-background);
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: var(--color-surface);
    border-right: 1px solid var(--color-border);
}

[data-testid="stSidebar"] .element-container {
    padding: 0.5rem 1rem;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: var(--color-text-primary) !important;
    font-weight: 600 !important;
}

h1 {
    font-size: 2.25rem !important;
    margin-bottom: 1.5rem !important;
}

h2 {
    font-size: 1.875rem !important;
    margin-bottom: 1rem !important;
}

h3 {
    font-size: 1.5rem !important;
    margin-bottom: 0.75rem !important;
}

/* Cards - Streamlit containers */
.element-container > div[data-testid="stVerticalBlock"] {
    background-color: var(--color-surface);
    border: 1px solid var(--color-surface-light);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    margin-bottom: var(--spacing-md);
    transition: all 0.2s ease;
}

/* Metrics */
[data-testid="stMetric"] {
    background-color: var(--color-surface);
    border: 1px solid var(--color-surface-light);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    transition: all 0.2s ease;
}

[data-testid="stMetric"]:hover {
    border-color: var(--color-primary);
    transform: translateY(-2px);
    box-shadow: var(--shadow-glow);
}

[data-testid="stMetricLabel"] {
    color: var(--color-text-secondary) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

[data-testid="stMetricValue"] {
    color: var(--color-text-primary) !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--color-primary), var(--color-primary-dark));
    color: white;
    border: none;
    border-radius: var(--radius-md);
    padding: 0.75rem 1.5rem;
    font-weight: 600;
    font-size: 0.875rem;
    transition: all 0.2s ease;
    box-shadow: var(--shadow-md);
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow);
}

.stButton > button:active {
    transform: translateY(0);
}

/* Input fields */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div > select {
    background-color: var(--color-background);
    border: 1px solid var(--color-surface-light);
    color: var(--color-text-primary);
    border-radius: var(--radius-md);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    transition: all 0.2s ease;
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stSelectbox > div > div > select:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Checkboxes */
.stCheckbox {
    color: var(--color-text-primary);
}

.stCheckbox > label {
    font-weight: 500;
}

/* Radio buttons */
.stRadio > label {
    color: var(--color-text-primary);
    font-weight: 500;
}

/* Sliders */
.stSlider > div > div > div {
    background-color: var(--color-surface-light);
}

.stSlider > div > div > div > div {
    background-color: var(--color-primary);
}

/* Dataframes */
.stDataFrame {
    border: 1px solid var(--color-surface-light);
    border-radius: var(--radius-lg);
    overflow: hidden;
}

/* Status containers */
.stStatus {
    background-color: var(--color-surface);
    border: 1px solid var(--color-surface-light);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
}

/* Success messages */
.stSuccess {
    background-color: rgba(34, 197, 94, 0.1);
    border-left: 4px solid var(--color-success);
    color: var(--color-success);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}

/* Warning messages */
.stWarning {
    background-color: rgba(249, 115, 22, 0.1);
    border-left: 4px solid var(--color-warning);
    color: var(--color-warning);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}

/* Error messages */
.stError {
    background-color: rgba(239, 68, 68, 0.1);
    border-left: 4px solid var(--color-error);
    color: var(--color-error);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}

/* Info messages */
.stInfo {
    background-color: rgba(59, 130, 246, 0.1);
    border-left: 4px solid var(--color-info);
    color: var(--color-info);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}

/* Expander */
.streamlit-expanderHeader {
    background-color: var(--color-surface);
    border: 1px solid var(--color-surface-light);
    border-radius: var(--radius-md);
    color: var(--color-text-primary);
    font-weight: 600;
}

.streamlit-expanderHeader:hover {
    border-color: var(--color-primary);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background-color: var(--color-surface);
    border-radius: var(--radius-lg);
    padding: 0.5rem;
}

.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    font-weight: 500;
    padding: 0.75rem 1.5rem;
    transition: all 0.2s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    background-color: var(--color-surface-light);
    color: var(--color-text-primary);
}

.stTabs [aria-selected="true"] {
    background-color: var(--color-primary) !important;
    color: white !important;
}

/* Spinner */
.stSpinner > div {
    border-color: var(--color-primary) !important;
}

/* Divider */
hr {
    border-color: var(--color-border);
    margin: var(--spacing-lg) 0;
}

/* Code blocks */
code {
    background-color: var(--color-surface);
    color: var(--color-primary-light);
    padding: 0.25rem 0.5rem;
    border-radius: var(--radius-sm);
    font-size: 0.875rem;
}

pre {
    background-color: var(--color-surface);
    border: 1px solid var(--color-surface-light);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--color-background);
}

::-webkit-scrollbar-thumb {
    background: var(--color-surface-light);
    border-radius: var(--radius-sm);
}

::-webkit-scrollbar-thumb:hover {
    background: var(--color-border);
}

/* Custom badge classes */
.badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 0.25rem;
}

.badge-success {
    background-color: rgba(34, 197, 94, 0.2);
    color: var(--color-success);
}

.badge-warning {
    background-color: rgba(249, 115, 22, 0.2);
    color: var(--color-warning);
}

.badge-error {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--color-error);
}

.badge-info {
    background-color: rgba(59, 130, 246, 0.2);
    color: var(--color-info);
}

/* Loading animation */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.loading {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Hover lift effect */
.hover-lift {
    transition: transform 0.2s ease;
}

.hover-lift:hover {
    transform: translateY(-2px);
}

/* Glassmorphism effect */
.glass {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
</style>
"""
