<template>
  <!-- No chrome at all: for pages that are embedded elsewhere or stand alone
       for people without an account (e.g. a customer support widget). -->
  <main class="min-h-screen bg-background text-foreground">
    <slot />
  </main>
</template>
