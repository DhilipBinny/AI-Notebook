# Typography System Reference

## Design Principles
- **Base size**: 14px (code input)
- **Scale ratio**: Major Second (1.125)
- **Grid**: 4px alignment where possible
- **Line heights**: WCAG 1.5× minimum for readability

## Standard Mode (Default)

| Component | Size | Line Height | CSS Variable |
|-----------|------|-------------|--------------|
| **H1** | 1.43em (~20px) | 1.3 | `--size-h1`, `--lh-h1` |
| **H2** | 1.29em (~18px) | 1.35 | `--size-h2`, `--lh-h2` |
| **H3** | 1.14em (~16px) | 1.4 | `--size-h3`, `--lh-h3` |
| **H4** | 1em (~14px) | 1.4 | `--size-h4` |
| **Markdown Body** | 15px | 1.6 | `--size-prose`, `--lh-prose` |
| **Code Input** | 14px | 1.5 | `--size-code`, `--lh-code` |
| **AI Response/Chat** | 14px | 1.55 | `--size-chat`, `--lh-chat` |
| **Code Output** | 13px | 1.4 | `--size-output`, `--lh-output` |
| **Meta/Status** | 12px | 1.2 | `--size-meta` |

## Cozy Mode (Reading/Tutorial)

| Component | Size | Line Height |
|-----------|------|-------------|
| **Markdown Body** | 16px | 1.65 |
| **Code Input** | 15px | 1.55 |
| **AI Response/Chat** | 15px | 1.6 |
| **Code Output** | 14px | 1.5 |

## Compact Mode (Data Science/DevOps)

| Component | Size | Line Height |
|-----------|------|-------------|
| **Markdown Body** | 14px | 1.5 |
| **Code Input** | 13px | 1.45 |
| **AI Response/Chat** | 13px | 1.45 |
| **Code Output** | 12px | 1.35 |

## Font Families

```css
--font-body: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-code: 'JetBrains Mono', 'Fira Code', 'SF Mono', 'Monaco', 'Menlo', monospace;
```

## Usage Guidelines

### Notebook Components
- **Code cells**: Use `--size-code` and `--font-code`
- **Markdown cells**: Use `--size-prose` and `--font-body`
- **AI cells/Chat**: Use `--size-chat` (matches code for consistency)
- **Cell output**: Use `--size-output` (denser for terminal-like feel)
- **Headers/badges**: Use `--size-meta`

### Headings
- Markdown cells and AI responses share the same heading scale
- Uses CSS variables (`--size-h1` through `--size-h4`)
- Scales with density mode selection

## Sources
- [Nord Design System](https://nordhealth.design/typography/) - 14px base for data-dense UIs
- [Design Shack Typography Guide](https://designshack.net/articles/typography/guide-to-responsive-typography-sizing-and-scales/)
- [Jupyter Typography Best Practices](http://slendermeans.org/better-typography-for-ipython-notebooks.html)
