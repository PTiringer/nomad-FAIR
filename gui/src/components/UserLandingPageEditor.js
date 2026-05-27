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
  Paper,
  TextField,
  Typography,
  makeStyles
} from '@material-ui/core'
import { DoesNotExist, useApi } from './api'
import { useErrors } from './errors'
import Page from './Page'

const template = `widgets:
  - type: hero
    title: Welcome back, {{displayName}}
    text: Customize this page by editing your personal YAML configuration.
    actions:
      - label: Open all projects
        to: /user/uploads
        variant: contained
  - type: recent_uploads
    title: Recent projects
    limit: 10
    empty_text: You do not have any projects yet.
    empty_action:
      label: Go to projects
      to: /user/uploads
`

const useStyles = makeStyles(theme => ({
  editorCard: {
    padding: theme.spacing(3)
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
      <Typography variant="h4" gutterBottom>
        Edit landing page YAML
      </Typography>
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
