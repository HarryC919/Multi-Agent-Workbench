import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { SkillsManager } from '@/components/SkillsManager'

// Mock the skills API module.
vi.mock('@/api/skills', () => ({
  fetchSkills: vi.fn(),
  fetchMarkdownSkill: vi.fn(),
  createMarkdownSkill: vi.fn(),
  updateMarkdownSkill: vi.fn(),
  deleteMarkdownSkill: vi.fn(),
  reloadSkills: vi.fn(),
}))

import {
  fetchSkills,
  fetchMarkdownSkill,
  createMarkdownSkill,
  updateMarkdownSkill,
  deleteMarkdownSkill,
} from '@/api/skills'

const mockedFetchSkills = vi.mocked(fetchSkills)
const mockedFetchMarkdownSkill = vi.mocked(fetchMarkdownSkill)
const mockedCreateMarkdownSkill = vi.mocked(createMarkdownSkill)
const mockedUpdateMarkdownSkill = vi.mocked(updateMarkdownSkill)
const mockedDeleteMarkdownSkill = vi.mocked(deleteMarkdownSkill)

const PY_SKILL = { name: 'echo', description: 'Echo input', source: 'python' as const }
const MD_SKILL = {
  name: 'translator',
  description: 'Translate text',
  source: 'markdown' as const,
}
const MD_SOURCE = { name: 'translator', description: 'Translate text', content: 'You are a translator.' }

describe('SkillsManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedFetchSkills.mockResolvedValue([PY_SKILL, MD_SKILL])
    mockedFetchMarkdownSkill.mockResolvedValue(MD_SOURCE)
    mockedCreateMarkdownSkill.mockResolvedValue({ name: 'summarizer' })
    mockedUpdateMarkdownSkill.mockResolvedValue({ name: 'translator' })
    mockedDeleteMarkdownSkill.mockResolvedValue({ deleted: 'translator' })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the skills list with source badges on open', async () => {
    render(<SkillsManager open={true} onClose={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText('translator')).toBeInTheDocument()
    })
    expect(screen.getByText('echo')).toBeInTheDocument()
    expect(screen.getByText('MD')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText(/共 2 个技能/)).toBeInTheDocument()
  })

  it('creates a markdown skill via the form', async () => {
    render(<SkillsManager open={true} onClose={() => {}} />)
    await waitFor(() => expect(mockedFetchSkills).toHaveBeenCalled())

    fireEvent.click(screen.getByText('新建技能'))
    fireEvent.change(screen.getByPlaceholderText('如：translator'), {
      target: { value: 'summarizer' },
    })
    fireEvent.change(screen.getByPlaceholderText(/一句话说明/), {
      target: { value: 'Summarize text' },
    })
    fireEvent.change(screen.getByPlaceholderText(/system prompt/), {
      target: { value: 'You summarize text.' },
    })
    fireEvent.click(screen.getByText('保存'))

    await waitFor(() => expect(mockedCreateMarkdownSkill).toHaveBeenCalled())
    expect(mockedCreateMarkdownSkill).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'summarizer',
        description: 'Summarize text',
        content: 'You summarize text.',
      }),
    )
  })

  it('opens a markdown skill for editing and pre-fills the form', async () => {
    render(<SkillsManager open={true} onClose={() => {}} />)
    await waitFor(() => screen.getByText('translator'))

    fireEvent.click(screen.getByText('translator'))
    await waitFor(() => expect(mockedFetchMarkdownSkill).toHaveBeenCalledWith('translator'))

    // The edit view shows the pre-filled content.
    await waitFor(() => {
      expect(screen.getByDisplayValue('translator')).toBeInTheDocument()
    })
    expect(screen.getByDisplayValue('Translate text')).toBeInTheDocument()
    expect(screen.getByDisplayValue('You are a translator.')).toBeInTheDocument()
  })

  it('does not open edit for Python skills', async () => {
    render(<SkillsManager open={true} onClose={() => {}} />)
    await waitFor(() => screen.getByText('echo'))

    // Click the Python skill - it should be disabled.
    const echoButton = screen.getByText('echo').closest('button')!
    expect(echoButton).toBeDisabled()
    fireEvent.click(echoButton)
    expect(mockedFetchMarkdownSkill).not.toHaveBeenCalled()
  })

  it('confirms before deleting a markdown skill', async () => {
    render(<SkillsManager open={true} onClose={() => {}} />)
    await waitFor(() => screen.getByText('translator'))
    fireEvent.click(screen.getByText('translator'))
    await waitFor(() => screen.getByDisplayValue('translator'))

    // Click delete in the edit view.
    fireEvent.click(screen.getByText('删除'))
    await waitFor(() => screen.getByText('删除该技能？'))
    fireEvent.click(screen.getByText('确认删除'))

    await waitFor(() =>
      expect(mockedDeleteMarkdownSkill).toHaveBeenCalledWith('translator'),
    )
  })

  it('updates a markdown skill on save', async () => {
    render(<SkillsManager open={true} onClose={() => {}} />)
    await waitFor(() => screen.getByText('translator'))
    fireEvent.click(screen.getByText('translator'))
    await waitFor(() => screen.getByDisplayValue('translator'))

    // Change the content and save.
    const textarea = screen.getByDisplayValue('You are a translator.') as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: 'You are a better translator.' } })
    fireEvent.click(screen.getByText('保存'))

    await waitFor(() => expect(mockedUpdateMarkdownSkill).toHaveBeenCalled())
    expect(mockedUpdateMarkdownSkill).toHaveBeenCalledWith(
      'translator',
      expect.objectContaining({ content: 'You are a better translator.' }),
    )
  })
})
