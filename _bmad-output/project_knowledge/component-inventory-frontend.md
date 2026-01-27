# Component Inventory - Frontend

**Framework:** Next.js 14
**Styling:** Tailwind CSS

## Dashboard Components
High-level widgets used in the main trading dashboard.

| Component | Description |
| :--- | :--- |
| `ActivePosition.tsx` | Details of a single open position (PnL, Size, Entry) |
| `ActivePositionsList.tsx` | Container/List for active positions |
| `ConfigPanel.tsx` | Main configuration area for bot settings |
| `ControlButtons.tsx` | Start/Stop/Panic engine controls |
| `CopilotCard.tsx` | AI insights display for active positions |
| `EquityChart.tsx` | Historical equity/balance visualization |
| `HealthMetrics.tsx` | System health indicators (Latency, API status) |
| `MarketAnalysis.tsx` | Multi-timeframe market sentiment display |
| `NotificationLog.tsx` | Scrollable log of bot activities and signals |
| `PerformanceChart.tsx` | Detailed performance metrics chart |
| `PnLCard.tsx` | Simple card showing daily PnL |
| `PositionCopilot.tsx` | Specialized advice view for position management |
| `PriceChart.tsx` | Real-time price chart for active symbol |
| `StrategySelector.tsx` | Dropdown/UI to select active trading strategy |
| `SystemStatusBanner.tsx` | Global status alerts (e.g., "Bot Stopped") |

## Dialogs & Settings
| Component | Description |
| :--- | :--- |
| `AdvancedSettings.tsx` | Modal/Panel for deep configuration (Risk, AI parameters) |

## UI Primitives (`components/ui/`)
Reusable base components.
- `button.tsx`: Standardized button styles
- `dialog.tsx`: Modal dialog wrappers
- `StatusPill.tsx`: Small status indicator (e.g., "Running", "Stopped")
