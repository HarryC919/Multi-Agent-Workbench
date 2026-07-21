import { describe, it, expect, beforeEach, afterEach, vi, type MockInstance } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { KnowledgeBaseManager } from '@/components/KnowledgeBaseManager'
import { useWorkspaceStore } from '@/store/workspaceStore'

// Mock the knowledge API module so we control list/create/delete/upload/listDocs.
vi.mock('@/api/knowledge', () => ({
  fetchKnowledgeBases: vi.fn(),
  createKnowledgeBase: vi.fn(),
  deleteKnowledgeBase: vi.fn(),
  listDocuments: vi.fn(),
  deleteDocument: vi.fn(),
  uploadDocument: vi.fn(),
}))

import {
  fetchKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  listDocuments,
  deleteDocument,
  uploadDocument,
} from '@/api/knowledge'

// `vi.mocked` gives the imports their mock-instance types so .mockResolvedValue
// etc. type-check under tsc (the build includes test files).
const mockedFetchKnowledgeBases = vi.mocked(fetchKnowledgeBases)
const mockedCreateKnowledgeBase = vi.mocked(createKnowledgeBase)
const mockedDeleteKnowledgeBase = vi.mocked(deleteKnowledgeBase)
const mockedListDocuments = vi.mocked(listDocuments)
const mockedDeleteDocument = vi.mocked(deleteDocument)
const mockedUploadDocument = vi.mocked(uploadDocument)

const KB = {
  id: 'kb-1',
  name: '我的笔记',
  description: 'desc',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
  documentCount: 0,
}

describe('KnowledgeBaseManager', () => {
  let fetchSpy: MockInstance

  beforeEach(() => {
    vi.clearAllMocks()
    mockedFetchKnowledgeBases.mockResolvedValue([KB])
    mockedCreateKnowledgeBase.mockResolvedValue(KB)
    mockedDeleteKnowledgeBase.mockResolvedValue({ deleted: true })
    mockedListDocuments.mockResolvedValue([])
    mockedDeleteDocument.mockResolvedValue({ deleted: true })
    mockedUploadDocument.mockResolvedValue({
      id: 'd1',
      knowledgeBaseId: 'kb-1',
      filename: 'notes.md',
      sha256: 'abc',
      createdAt: '2026-01-01T00:00:00Z',
      textLength: 42,
    })

    useWorkspaceStore.setState({ knowledgeBases: [], selectedKbId: '' })

    // The manager uses store.loadKnowledgeBases which dynamically imports the
    // API module; spy on global fetch as a backstop for any direct fetch calls.
    fetchSpy = vi.spyOn(global, 'fetch')
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    useWorkspaceStore.setState({ knowledgeBases: [], selectedKbId: '' })
  })

  it('renders the KB list on open', async () => {
    render(<KnowledgeBaseManager open={true} onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('我的笔记')).toBeInTheDocument()
    })
    expect(screen.getByText(/共 1 个知识库/)).toBeInTheDocument()
  })

  it('creates a knowledge base via the form', async () => {
    mockedCreateKnowledgeBase.mockResolvedValue({ ...KB, id: 'kb-2', name: '新笔记' })
    render(<KnowledgeBaseManager open={true} onClose={() => {}} />)

    await waitFor(() => expect(mockedFetchKnowledgeBases).toHaveBeenCalled())

    fireEvent.click(screen.getByText('新建知识库'))
    fireEvent.change(screen.getByPlaceholderText('如：我的笔记'), {
      target: { value: '新笔记' },
    })
    fireEvent.click(screen.getByText('保存'))

    await waitFor(() => expect(mockedCreateKnowledgeBase).toHaveBeenCalled())
    expect(mockedCreateKnowledgeBase).toHaveBeenCalledWith(
      expect.objectContaining({ name: '新笔记' }),
    )
  })

  it('opens a KB and uploads a document', async () => {
    render(<KnowledgeBaseManager open={true} onClose={() => {}} />)
    await waitFor(() => screen.getByText('我的笔记'))

    fireEvent.click(screen.getByText('我的笔记'))
    await waitFor(() => expect(mockedListDocuments).toHaveBeenCalledWith('kb-1'))

    // The upload button triggers a hidden file input.
    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement
    expect(fileInput).not.toBeNull()

    const file = new File(['# 标题\n内容'], 'notes.md', { type: 'text/markdown' })
    fireEvent.change(fileInput, { target: { files: [file] } })

    await waitFor(() => expect(mockedUploadDocument).toHaveBeenCalledWith('kb-1', file))
  })

  it('confirms before deleting a knowledge base', async () => {
    render(<KnowledgeBaseManager open={true} onClose={() => {}} />)
    await waitFor(() => screen.getByText('我的笔记'))

    // Click the trash icon (only one at the KB-list level).
    const trashButtons = screen.getAllByRole('button')
    const trashBtn = trashButtons.find((b) => b.querySelector('svg.lucide-trash2'))
    fireEvent.click(trashBtn!)

    await waitFor(() => screen.getByText('删除该知识库？'))
    fireEvent.click(screen.getByText('确认删除'))

    await waitFor(() => expect(mockedDeleteKnowledgeBase).toHaveBeenCalledWith('kb-1'))
  })
})
