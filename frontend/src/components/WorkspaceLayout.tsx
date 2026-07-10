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
  const { sendMessage } = useChatStream()
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

  const handleSend = (content: string) => {
    if (!store.selectedModel) {
      useToastStore.getState().addToast('请先选择一个模型', 'warning')
      return
    }
    sendMessage(content, store.attachedFiles)
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
          effort={store.effort}
          attachedFiles={store.attachedFiles}
          isStreaming={store.isStreaming}
          onModelChange={store.setSelectedModel}
          onEffortChange={store.setEffort}
          onAttachFile={store.attachFile}
          onRemoveFile={store.removeFile}
          onSend={handleSend}
        />
      </div>
      <ToastContainer />
    </div>
  )
}
