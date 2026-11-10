import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: () => import('../views/ChatView.vue') },
    { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue') },
    { path: '/analysis/:taskId', name: 'analysis', component: () => import('../views/AnalysisWorkbench.vue') },
    { path: '/screener', name: 'screener', component: () => import('../views/ScreenerWorkbench.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
