import { useEffect } from 'react'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { useToastStore } from '@/store/toastStore'

export function useConversation() {
  const store = useWorkspaceStore()

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        await store.loadConversations()
        if (cancelled) return
        await store.loadModels()
        if (cancelled) return
        await store.loadKnowledgeBases()
      } catch (error) {
        if (cancelled) return
        useToastStore
          .getState()
          .addToast(error instanceof Error ? error.message : 'Failed to load data', 'error')
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [])

  return {
    conversations: store.conversations,
    activeId: store.activeId,
    currentConversation: store.currentConversation,
    isLoadingConversation: store.isLoadingConversation,
    setActive: store.setActive,
    createConversation: store.createConversation,
    renameConversation: store.renameConversation,
    deleteConversation: store.deleteConversation,
  }
}
