import { useWorkspaceStore } from '@/store/workspaceStore'
import { useToastStore } from '@/store/toastStore'
import { useConversation } from '@/hooks/useConversation'
import { useChatStream } from '@/hooks/useChatStream'
import { ChatHeader } from './ChatHeader'
import { EmptyState } from './EmptyState'
import { InputArea } from './InputArea'
import { MessageList } from './MessageList'
import { Sidebar } from './Sidebar'
import { ToastContainer } from './ToastContainer'

export function WorkspaceLayout() {
  const store = useWorkspaceStore()
  const { sendMessage, abort } = useChatStream()
  const {
    conversations,
    activeId,
    currentConversation,
    isLoadingConversation,
    setActive,
    createConversation,
    renameConversation,
    deleteConversation,
  } = useConversation()

  const handleSend = async (content: string) => {
    if (!store.selectedModel) {
      useToastStore.getState().addToast('请先选择一个模型', 'warning')
      return
    }
    // Agent mode with no KB selected: retrieve_notes can't be armed, so the
    // backend degrades to a direct answer (no death-loop). Surface this so
    // the user knows this turn won't search their notes — but don't block
    // the send, since not every agent question needs retrieval.
    if (store.agentMode && !store.selectedKbId) {
      useToastStore
        .getState()
        .addToast('未选择知识库：本轮 Agent 将直接作答，无法检索笔记', 'warning')
    }
    // Starting from the empty/landing state: create a conversation first so
    // the first message lands in a real conversation (and triggers title
    // auto-generation on the backend). Use the returned id explicitly —
    // reading store.activeId here would hit a stale-closure value captured at
    // render time, before the async createConversation resolved.
    let conversationId = useWorkspaceStore.getState().activeId
    if (!conversationId) {
      conversationId = await createConversation()
    }
    sendMessage(content, store.attachedFiles, conversationId ?? undefined)
    store.clearInput()
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      <Sidebar
        conversations={conversations ?? []}
        activeId={activeId}
        onSelect={setActive}
        onNewConversation={createConversation}
        onRename={renameConversation}
        onDelete={deleteConversation}
      />
      <div className="flex flex-1 flex-col">
        <ChatHeader
          title={currentConversation?.title || 'AI Chat Workbench'}
          models={store.models}
          selectedModel={store.selectedModel}
          onModelChange={store.setSelectedModel}
        />
        <div className="flex-1 overflow-hidden">
          {isLoadingConversation ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              加载中...
            </div>
          ) : !currentConversation ? (
            <EmptyState onNewConversation={createConversation} />
          ) : (
            <MessageList messages={currentConversation.messages} />
          )}
        </div>
        <InputArea
          models={store.models}
          selectedModel={store.selectedModel}
          thinkingEnabled={store.thinkingEnabled}
          agentMode={store.agentMode}
          attachedFiles={store.attachedFiles}
          isStreaming={store.isStreaming}
          onModelChange={store.setSelectedModel}
          onThinkingToggle={store.setThinkingEnabled}
          onAgentModeToggle={store.setAgentMode}
          onAttachFile={store.attachFile}
          onRemoveFile={store.removeFile}
          onSend={handleSend}
          onAbort={abort}
        />
      </div>
      <ToastContainer />
    </div>
  )
}
