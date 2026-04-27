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
import React, { useEffect, useState } from 'react'
import YAML from 'yaml'
import {
  Box,
  Button,
  IconButton,
  Paper,
  TextField,
  Tooltip,
  Typography,
  makeStyles
} from '@material-ui/core'
import HelpOutlineIcon from '@material-ui/icons/HelpOutline'
import { DoesNotExist, useApi } from './api'
import { useErrors } from './errors'
import Page from './Page'

const template = `sidebar:
  title: Workspace
  size: sm
  items:
    - type: link
      label: Uploads
      to: /user/uploads
      icon: cloud_upload
    - type: link
      label: Datasets
      to: /user/datasets
      icon: storage
    - type: link
      label: Search your data
      to: /user/search
      icon: search
    - type: divider
    - type: markdown
      text: Add personal links and notes here from the same YAML file.

widgets:
  - type: hero
    title: Welcome back, {{displayName}}
    text: Customize this page by editing your personal YAML configuration.
    actions:
      - label: Open all uploads
        to: /user/uploads
        variant: contained
  - type: recent_uploads
    title: Recent uploads
    limit: 10
    empty_text: You do not have any uploads yet.
    empty_action:
      label: Go to uploads
      to: /user/uploads
  - type: markdown
    text: Use this space to add a short personal note, links, or instructions for your landing page.
  - type: notes
    title: Notes
    content: <p>Use this rich-text area to keep personal notes, highlight links, or add formatted instructions for your landing page.</p>
`

const useStyles = makeStyles(theme => ({
  editorCard: {
    padding: theme.spacing(3)
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: theme.spacing(1)
  },
  editor: {
    marginTop: theme.spacing(2)
  },
  actions: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: theme.spacing(2),
    marginTop: theme.spacing(2)
  },
  helpContent: {
    maxWidth: 420
  }
}))

export default function UserLandingPageEditor() {
  const classes = useStyles()
  const { api } = useApi()
  const errors = useErrors()
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    api.get('users/me/landing-page')
      .then(content => {
        setValue(content || template)
        setLoading(false)
      })
      .catch(error => {
        if (error instanceof DoesNotExist) {
          setValue(template)
          setLoading(false)
          return
        }
        setLoading(false)
        errors.raiseError(error)
      })
  }, [api, errors])

  const handleSave = () => {
    setStatus('')
    try {
      YAML.parse(value)
    } catch (error) {
      errors.raiseError(error)
      return
    }

    setSaving(true)
    api.put('users/me/landing-page', value, {
      headers: {
        'Content-Type': 'application/yaml',
        accept: 'application/yaml'
      }
    })
      .then(() => {
        setStatus('Saved.')
      })
      .catch(errors.raiseError)
      .finally(() => {
        setSaving(false)
      })
  }

  return <Page limitedWidth loading={loading}>
    <Paper className={classes.editorCard}>
      <Box className={classes.header} mb={1}>
        <Typography variant="h4">
          Edit landing page YAML
        </Typography>
        <Tooltip
          arrow
          placement="right"
          interactive
          title={
            <Box className={classes.helpContent}>
              <Typography variant="subtitle2" gutterBottom>
                How to use this editor
              </Typography>
              <Typography variant="body2" gutterBottom>
                Define your page under a top-level <code>widgets:</code> list. Each widget must use <code>type:</code>.
              </Typography>
              <Typography variant="body2" gutterBottom>
                Define an optional left sidebar under top-level <code>sidebar:</code>. Sidebar item types are <code>link</code>, <code>markdown</code>, <code>text</code>, and <code>divider</code>.
              </Typography>
              <Typography variant="body2" gutterBottom>
                Available widget types: <code>hero</code>, <code>markdown</code>, <code>notes</code>, <code>button</code>, and <code>recent_uploads</code>.
              </Typography>
              <Typography variant="body2" gutterBottom>
                You can use placeholders like <code>{'{{displayName}}'}</code>, <code>{'{{username}}'}</code>, and <code>{'{{email}}'}</code>.
              </Typography>
              <Typography variant="body2" gutterBottom>
                The <code>notes</code> widget uses the rich-text editor on the landing page itself. In YAML, its formatted content is stored in <code>content</code>.
              </Typography>
              <Typography variant="body2">
                Example:
                <br />
                <code>{'sidebar:'}</code>
                <br />
                <code>{'  title: Workspace'}</code>
                <br />
                <code>{'  items:'}</code>
                <br />
                <code>{'    - type: link'}</code>
                <br />
                <code>{'      label: Uploads'}</code>
                <br />
                <code>{'      to: /user/uploads'}</code>
                <br />
                <code>{'      icon: cloud_upload'}</code>
                <br />
                <br />
                <code>{'- type: markdown'}</code>
                <br />
                <code>{'  text: |'}</code>
                <br />
                <code>{'    ## Welcome'}</code>
                <br />
                <code>{'    Add links or notes here.'}</code>
                <br />
                <br />
                <code>{'- type: notes'}</code>
                <br />
                <code>{'  title: Notes'}</code>
                <br />
                <code>{'  content: <p>Rich text content</p>'}</code>
              </Typography>
            </Box>
          }
        >
          <IconButton size="small" aria-label="Landing page editor help">
            <HelpOutlineIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Typography variant="body1">
        This file is stored in your user-scoped filesystem area and overrides the default landing page only for your account.
      </Typography>
      <TextField
        className={classes.editor}
        label="user-home.yaml"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        variant="outlined"
        fullWidth
        multiline
        rowsMin={24}
      />
      <Box className={classes.actions}>
        <Typography color="textSecondary">
          {status}
        </Typography>
        <Button
          color="primary"
          variant="contained"
          onClick={handleSave}
          disabled={saving || loading}
        >
          Save YAML
        </Button>
      </Box>
    </Paper>
  </Page>
}
