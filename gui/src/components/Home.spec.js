/*
 * Copyright The NOMAD Authors.
 *
 * This file is part of NOMAD. See https://nomad-lab.eu for further info.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import React from 'react'
import 'regenerator-runtime/runtime'
import { waitFor } from '@testing-library/react'
import { renderNoAPI, screen } from './conftest.spec'
import Home from './Home'
import { useApi } from './api'
import { useErrors } from './errors'

jest.mock('./api', () => ({
  DoesNotExist: class DoesNotExist extends Error {},
  useApi: jest.fn()
}))

jest.mock('./errors', () => ({
  useErrors: jest.fn()
}))

describe('<Home />', () => {
  it('renders configured sidebar links to internal app routes', async () => {
    useApi.mockReturnValue({
      api: {
        keycloak: {authenticated: true},
        get: jest.fn((path) => {
          if (path === 'users/me/landing-page') {
            return Promise.resolve(`
sidebar:
  title: Workspace
  items:
    - type: link
      label: Uploads
      to: /user/uploads
      icon: cloud_upload
    - type: link
      label: Datasets
      route: /user/datasets
    - type: link
      label: Docs
      href: https://example.com/docs
widgets:
  - type: markdown
    text: Welcome
`)
          }
          return Promise.resolve({data: []})
        })
      },
      user: {
        name: 'Test User',
        preferred_username: 'test'
      }
    })
    useErrors.mockReturnValue({raiseError: jest.fn()})

    renderNoAPI(<Home />)

    await waitFor(() => {
      expect(screen.getByText('Workspace')).toBeInTheDocument()
    })

    expect(screen.getByText('Uploads').closest('a')).toHaveAttribute('href', '/user/uploads')
    expect(screen.getByText('Datasets').closest('a')).toHaveAttribute('href', '/user/datasets')
    expect(screen.getByText('Docs').closest('a')).toHaveAttribute('href', 'https://example.com/docs')
  })
})
