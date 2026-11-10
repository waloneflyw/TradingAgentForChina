import { defineStore } from 'pinia'

export type ThemeMode = 'system' | 'light' | 'dark'

const KEY = 'ashare-theme-mode'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: (localStorage.getItem(KEY) as ThemeMode) || 'system',
  }),
  actions: {
    apply() {
      const root = document.documentElement
      if (this.mode === 'system') {
        root.removeAttribute('data-theme')
      } else {
        root.setAttribute('data-theme', this.mode)
      }
      localStorage.setItem(KEY, this.mode)
    },
    setMode(mode: ThemeMode) {
      this.mode = mode
      this.apply()
    },
  },
})
