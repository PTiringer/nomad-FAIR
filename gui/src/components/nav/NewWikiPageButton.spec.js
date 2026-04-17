import React from 'react'
import { fireEvent, renderNoAPI, screen, waitFor } from '../conftest.spec'
import NewWikiPageButton from './NewWikiPageButton'
import { useApi } from '../api'
import { useErrors } from '../errors'

jest.mock('../api', () => ({
  useApi: jest.fn()
}))

jest.mock('../errors', () => ({
  useErrors: jest.fn()
}))

describe('<NewWikiPageButton />', () => {
  afterEach(() => {
    jest.useRealTimers()
  }

  it('creates a new upload and wiki page entry', async () => {
    jest.useFakeTimers().setSystemTime(new Date('2026-04-08T13:45:00Z'))
    const post = jest.fn().mockResolvedValue({ upload_id: 'upload-1' })
    const put = jest.fn().mockResolvedValue({ processing: { entry_id: 'entry-1' } })
    const raiseError = jest.fn()

    useApi.mockReturnValue({
      api: {post, put},
      user: {sub: 'user-1', name: 'Missing name'}
    })
    useErrors.mockReturnValue({raiseError})

    renderNoAPI(<NewWikiPageButton />)

    fireEvent.click(screen.getByRole('button', { name: 'New Wiki Page' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/uploads'))
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith(
        'uploads/upload-1/raw/?file_name=home.archive.json&overwrite_if_exists=false&wait_for_processing=true',
        {
          data: {
            m_def: 'wiki_page.schema_packages.schema_package.WikiPage',
            name: 'Missing date time name',
            tags: ['wiki', 'knowledge-base']
          }
        }
      )
    )
    expect(raiseError).not.toHaveBeenCalled()
  })
})
