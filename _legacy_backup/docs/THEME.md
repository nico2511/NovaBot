# BoxProof Theme Documentation

## 🎨 Color Palette

### Primary Colors
```css
--color-primary: #3b82f6;      /* Blue 500 */
--color-primary-dark: #2563eb; /* Blue 600 */
--color-primary-light: #60a5fa;/* Blue 400 */
```

### Status Colors
```css
--color-success: #22c55e;      /* Green 500 */
--color-warning: #f97316;      /* Orange 500 */
--color-error: #ef4444;        /* Red 500 */
--color-info: #3b82f6;         /* Blue 500 */
```

### Neutral Colors (Dark Theme)
```css
--color-background: #0f172a;   /* Slate 900 */
--color-surface: #1e293b;      /* Slate 800 */
--color-surface-light: #334155;/* Slate 700 */
--color-border: #475569;       /* Slate 600 */
--color-text-primary: #f8fafc; /* Slate 50 */
--color-text-secondary: #cbd5e1;/* Slate 300 */
--color-text-muted: #94a3b8;   /* Slate 400 */
```

### Plan-Specific Colors
```css
--color-free: #64748b;         /* Slate 500 */
--color-pro: #22c55e;          /* Green 500 */
--color-og: #a855f7;           /* Purple 500 */
```

---

## 📐 Typography

### Font Family
```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

### Font Sizes
```css
--text-xs: 0.75rem;    /* 12px */
--text-sm: 0.875rem;   /* 14px */
--text-base: 1rem;     /* 16px */
--text-lg: 1.125rem;   /* 18px */
--text-xl: 1.25rem;    /* 20px */
--text-2xl: 1.5rem;    /* 24px */
--text-3xl: 1.875rem;  /* 30px */
--text-4xl: 2.25rem;   /* 36px */
```

### Font Weights
```css
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

---

## 🎯 Component Styles

### Card
```css
.card {
  background: #1e293b;           /* Slate 800 */
  border: 1px solid #334155;     /* Slate 700 */
  border-radius: 1rem;           /* 16px */
  padding: 1.5rem;               /* 24px */
}

.card-hover:hover {
  border-color: #3b82f6;         /* Blue 500 */
  transform: translateY(-2px);
  transition: all 0.2s ease;
}
```

### Buttons

#### Primary Button
```css
.btn-primary {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #ffffff;
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-weight: 600;
  transition: all 0.2s ease;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 25px rgba(59, 130, 246, 0.3);
}
```

#### Secondary Button
```css
.btn-secondary {
  background: #334155;           /* Slate 700 */
  color: #f8fafc;                /* Slate 50 */
  border: 1px solid #475569;     /* Slate 600 */
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: #475569;           /* Slate 600 */
  border-color: #64748b;         /* Slate 500 */
}
```

### Input Fields
```css
.input {
  background: #0f172a;           /* Slate 900 */
  border: 1px solid #334155;     /* Slate 700 */
  color: #f8fafc;                /* Slate 50 */
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  transition: all 0.2s ease;
}

.input:focus {
  outline: none;
  border-color: #3b82f6;         /* Blue 500 */
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.input::placeholder {
  color: #64748b;                /* Slate 500 */
}
```

### Badges
```css
.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;         /* Full rounded */
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-success {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.badge-warning {
  background: rgba(249, 115, 22, 0.2);
  color: #f97316;
}

.badge-error {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}
```

---

## 📏 Spacing System

```css
--spacing-1: 0.25rem;   /* 4px */
--spacing-2: 0.5rem;    /* 8px */
--spacing-3: 0.75rem;   /* 12px */
--spacing-4: 1rem;      /* 16px */
--spacing-5: 1.25rem;   /* 20px */
--spacing-6: 1.5rem;    /* 24px */
--spacing-8: 2rem;      /* 32px */
--spacing-10: 2.5rem;   /* 40px */
--spacing-12: 3rem;     /* 48px */
```

---

## 🔲 Border Radius

```css
--radius-sm: 0.25rem;   /* 4px */
--radius-md: 0.5rem;    /* 8px */
--radius-lg: 1rem;      /* 16px */
--radius-xl: 1.5rem;    /* 24px */
--radius-full: 9999px;  /* Full rounded */
```

---

## 🌑 Shadows

```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.15);
--shadow-glow: 0 0 20px rgba(59, 130, 246, 0.3);
```

---

## ⚡ Animations & Transitions

### Standard Transitions
```css
--transition-fast: 150ms ease;
--transition-base: 200ms ease;
--transition-slow: 300ms ease;
```

### Hover Effects
```css
.hover-lift:hover {
  transform: translateY(-2px);
  transition: transform 200ms ease;
}

.hover-scale:hover {
  transform: scale(1.02);
  transition: transform 200ms ease;
}
```

### Loading Animation
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.loading {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

---

## 🎨 Usage Examples

### Dashboard Card
```tsx
<div className="card card-hover p-6">
  <div className="flex items-center gap-4">
    <div className="p-3 bg-blue-500/10 text-blue-400 rounded-xl">
      <span className="text-2xl">📦</span>
    </div>
    <div>
      <p className="text-slate-400 text-xs font-medium">Total Expéditions</p>
      <h3 className="text-2xl font-bold text-white">42</h3>
    </div>
  </div>
</div>
```

### Status Badge
```tsx
<span className="badge badge-success">
  ✓ Actif
</span>
```

### Form Input
```tsx
<input
  type="text"
  className="input w-full"
  placeholder="Entrez votre email"
/>
```

---

## 🎯 Design Principles

1. **Dark-First Design**: All components are designed for dark mode
2. **Consistent Spacing**: Use the spacing system for all margins and paddings
3. **Subtle Animations**: Hover effects should be smooth and subtle
4. **High Contrast**: Ensure text is readable with proper contrast ratios
5. **Glassmorphism**: Use semi-transparent backgrounds with backdrop blur for depth
6. **Color Coding**: Use consistent colors for status (green=success, orange=warning, red=error)

---

## 📱 Responsive Breakpoints

```css
--breakpoint-sm: 640px;   /* Mobile */
--breakpoint-md: 768px;   /* Tablet */
--breakpoint-lg: 1024px;  /* Desktop */
--breakpoint-xl: 1280px;  /* Large Desktop */
```

---

## 🔧 Implementation Notes

- All colors use Tailwind CSS classes for consistency
- Custom components extend Tailwind's utility classes
- Use `className` composition for reusable styles
- Prefer CSS-in-JS or Tailwind over traditional CSS files
- Maintain semantic HTML for accessibility

---

## 📦 Reusability

This theme can be reused in other projects by:
1. Copying the color palette to your CSS variables
2. Using the same Tailwind configuration
3. Implementing the component styles as utility classes
4. Following the same spacing and typography system

**Tailwind Config Example:**
```js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
        surface: '#1e293b',
        background: '#0f172a',
      },
    },
  },
}
```
