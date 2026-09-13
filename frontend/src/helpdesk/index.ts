/**
 * Helpdesk module entry - registers everything the platform shell needs to
 * know about the product. Imported once from `src/main.ts`.
 */
import {
  BarChart3,
  BookOpen,
  Contact,
  Inbox,
  LayoutDashboard,
  MessagesSquare,
} from 'lucide-vue-next'
import { registerNavItems } from '@/platform/navigation'
import '@/helpdesk/notifications/ticketActivity'
import '@/helpdesk/notifications/ticketAssigned'

registerNavItems('main', [
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard, order: 10 },
  { to: '/tickets', labelKey: 'nav.tickets', icon: Inbox, order: 15, permission: 'read:ticket' },
  {
    to: '/contacts',
    labelKey: 'nav.contacts',
    icon: Contact,
    order: 20,
    permission: 'read:contact',
  },
  {
    to: '/knowledge-base',
    labelKey: 'nav.knowledgeBase',
    icon: BookOpen,
    order: 25,
    permission: 'manage:kb',
  },
  {
    to: '/reports',
    labelKey: 'nav.reports',
    icon: BarChart3,
    order: 28,
    permission: 'read:report',
  },
])

registerNavItems('manage', [
  {
    to: '/support-widget',
    labelKey: 'nav.supportSite',
    icon: MessagesSquare,
    order: 30,
    permission: 'manage:helpdesk',
  },
])
