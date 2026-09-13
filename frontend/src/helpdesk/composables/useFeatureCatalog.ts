import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  BarChart3,
  Bell,
  BookOpen,
  Globe,
  Inbox,
  MessagesSquare,
  ShieldCheck,
  Users,
} from 'lucide-vue-next'

/**
 * The feature catalog shared by the landing page and the dedicated features
 * page. Copy lives under the `landing.features` namespace.
 */
export function useFeatureCatalog() {
  const { t } = useI18n()

  const features = computed(() =>
    [
      { key: 'tickets', icon: Inbox },
      { key: 'widget', icon: MessagesSquare },
      { key: 'knowledgeBase', icon: BookOpen },
      { key: 'reports', icon: BarChart3 },
      { key: 'teams', icon: Users },
      { key: 'rbac', icon: ShieldCheck },
      { key: 'notifications', icon: Bell },
      { key: 'i18n', icon: Globe },
    ].map((feature) => ({
      ...feature,
      title: t(`landing.features.${feature.key}.title`),
      desc: t(`landing.features.${feature.key}.desc`),
    })),
  )

  return { features }
}
