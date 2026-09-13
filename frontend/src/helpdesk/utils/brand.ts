export const DEFAULT_BRAND_COLOR = '#293e70'

/**
 * Styles for a surface in an organization's brand color, with readable text:
 * dark on light colors, white on dark ones (perceived brightness).
 */
export function brandColors(color: string | null | undefined): {
  backgroundColor: string
  color: string
} {
  const background = color && /^#[0-9a-f]{6}$/i.test(color) ? color : DEFAULT_BRAND_COLOR
  const value = Number.parseInt(background.slice(1), 16)
  const [r, g, b] = [(value >> 16) & 255, (value >> 8) & 255, value & 255]
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return { backgroundColor: background, color: brightness > 150 ? '#131825' : '#ffffff' }
}
