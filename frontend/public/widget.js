/**
 * Support widget loader.
 *
 * Embed on any website with:
 *
 *   <script src="https://app.example.com/widget.js" data-site="your-support-address" async></script>
 *
 * Optional attributes: data-color="#293e70", data-locale="en" | "da",
 * data-position="left". The widget itself runs in an iframe served by the app,
 * so it never touches the host page's cookies, storage or styles.
 */
;(function () {
  var script = document.currentScript
  if (!script || window.__helpdeskWidgetLoaded) return
  window.__helpdeskWidgetLoaded = true

  var slug = script.getAttribute('data-site')
  if (!slug) {
    console.warn('[helpdesk] The widget script needs a data-site attribute.')
    return
  }

  var origin = new URL(script.src).origin
  var color = script.getAttribute('data-color') || '#293e70'
  var locale = script.getAttribute('data-locale') || (navigator.language || '').slice(0, 2)
  var side = script.getAttribute('data-position') === 'left' ? 'left' : 'right'
  var src =
    origin +
    '/widget/' +
    encodeURIComponent(slug) +
    (locale ? '?lang=' + encodeURIComponent(locale) : '')

  var CHAT_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
  var CLOSE_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>'

  var button = document.createElement('button')
  button.type = 'button'
  button.setAttribute('aria-label', 'Open support')
  button.setAttribute('aria-expanded', 'false')
  button.innerHTML = CHAT_ICON
  Object.assign(button.style, {
    position: 'fixed',
    bottom: '20px',
    width: '56px',
    height: '56px',
    border: '0',
    borderRadius: '50%',
    background: color,
    color: '#ffffff',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 4px 16px rgba(18, 23, 33, 0.24)',
    zIndex: '2147483000',
  })
  button.style[side] = '20px'

  var frame = document.createElement('iframe')
  frame.title = 'Support'
  Object.assign(frame.style, {
    position: 'fixed',
    bottom: '88px',
    width: '380px',
    height: '600px',
    maxWidth: 'calc(100vw - 40px)',
    maxHeight: 'calc(100vh - 108px)',
    border: '0',
    borderRadius: '12px',
    background: '#ffffff',
    boxShadow: '0 8px 32px rgba(18, 23, 33, 0.24)',
    display: 'none',
    zIndex: '2147483000',
  })
  frame.style[side] = '20px'

  var open = false

  function toggle(next) {
    open = next
    // Load the widget on first open so it costs the host page nothing until used.
    if (open && !frame.src) frame.src = src
    frame.style.display = open ? 'block' : 'none'
    button.innerHTML = open ? CLOSE_ICON : CHAT_ICON
    button.setAttribute('aria-expanded', String(open))
    button.setAttribute('aria-label', open ? 'Close support' : 'Open support')
  }

  button.addEventListener('click', function () {
    toggle(!open)
  })

  window.addEventListener('message', function (event) {
    if (event.origin !== origin || !event.data) return
    if (event.data.type === 'helpdesk:close') toggle(false)
  })

  function mount() {
    document.body.appendChild(frame)
    document.body.appendChild(button)
  }

  if (document.body) mount()
  else document.addEventListener('DOMContentLoaded', mount)
})()
