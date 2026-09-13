<template>
  <!-- The HTML is rendered by the API from Markdown with raw HTML disabled
       (backend src/helpdesk/markdown.py), so it is safe to insert as-is. -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="kb-content" v-html="html" />
</template>

<script setup lang="ts">
defineProps<{ html: string }>()
</script>

<style scoped>
.kb-content {
  font-size: 0.9375rem;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.kb-content :deep(p),
.kb-content :deep(ul),
.kb-content :deep(ol),
.kb-content :deep(pre),
.kb-content :deep(blockquote),
.kb-content :deep(table) {
  margin: 0 0 1em;
}
.kb-content :deep(h1),
.kb-content :deep(h2),
.kb-content :deep(h3),
.kb-content :deep(h4) {
  font-weight: 600;
  line-height: 1.3;
  margin: 1.5em 0 0.5em;
}
.kb-content :deep(h1) {
  font-size: 1.5em;
}
.kb-content :deep(h2) {
  font-size: 1.25em;
}
.kb-content :deep(h3) {
  font-size: 1.1em;
}
.kb-content :deep(> :first-child) {
  margin-top: 0;
}
.kb-content :deep(ul) {
  list-style: disc;
  padding-left: 1.5em;
}
.kb-content :deep(ol) {
  list-style: decimal;
  padding-left: 1.5em;
}
.kb-content :deep(li + li) {
  margin-top: 0.25em;
}
.kb-content :deep(a) {
  color: hsl(var(--primary));
  text-decoration: underline;
  text-underline-offset: 2px;
}
.kb-content :deep(code) {
  background: hsl(var(--muted));
  border-radius: 0.25rem;
  font-size: 0.875em;
  padding: 0.1em 0.3em;
}
.kb-content :deep(pre) {
  background: hsl(var(--muted));
  border-radius: 0.5rem;
  overflow-x: auto;
  padding: 0.75em 1em;
}
.kb-content :deep(pre code) {
  background: none;
  padding: 0;
}
.kb-content :deep(blockquote) {
  border-left: 3px solid hsl(var(--border));
  color: hsl(var(--muted-foreground));
  padding-left: 1em;
}
.kb-content :deep(table) {
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}
.kb-content :deep(th),
.kb-content :deep(td) {
  border: 1px solid hsl(var(--border));
  padding: 0.4em 0.75em;
  text-align: left;
}
.kb-content :deep(img) {
  border-radius: 0.5rem;
  max-width: 100%;
}
</style>
