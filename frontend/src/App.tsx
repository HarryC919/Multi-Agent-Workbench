import { useEffect, useState } from 'react'
import { WorkspaceLayout } from '@/components/WorkspaceLayout'
import { rehydrateWorkspaceStore } from '@/store/workspaceStore'

function App() {
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    rehydrateWorkspaceStore().then(() => setHydrated(true))
  }, [])

  if (!hydrated) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        Loading...
      </div>
    )
  }

  return <WorkspaceLayout />
}

export default App
