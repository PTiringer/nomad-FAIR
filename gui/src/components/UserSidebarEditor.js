/*
 * Copyright The NOMAD Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 */
import React, { useEffect, useState } from 'react'
import YAML from 'yaml'
import { Box, Button, Paper, TextField, Typography, makeStyles } from '@material-ui/core'
import { DoesNotExist, useApi } from './api'
import { useErrors } from './errors'
import Page from './Page'

export const sidebarTemplate = `title: My wiki pages
wiki_pages:
  enabled: true
  title: Wiki pages
  limit: 20
  empty_text: You do not have any wiki pages yet.
links: []
`

const useStyles = makeStyles(theme => ({
  card: { padding: theme.spacing(3) },
  editor: { marginTop: theme.spacing(2) },
  actions: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: theme.spacing(2),
    marginTop: theme.spacing(2)
  }
}))

export default function UserSidebarEditor() {
  const classes = useStyles()
  const { api } = useApi()
  const errors = useErrors()
  const [value, setValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    api.get('users/me/sidebar')
      .then(content => setValue(content || sidebarTemplate))
      .catch(error => {
        if (error instanceof DoesNotExist) {
          setValue(sidebarTemplate)
          return
        }
        errors.raiseError(error)
      })
      .finally(() => setLoading(false))
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
    api.put('users/me/sidebar', value, {
      headers: {'Content-Type': 'application/yaml', accept: 'application/yaml'}
    })
      .then(() => setStatus('Saved.'))
      .catch(errors.raiseError)
      .finally(() => setSaving(false))
  }

  return <Page limitedWidth loading={loading}>
    <Paper className={classes.card}>
      <Typography variant="h4" gutterBottom>Edit sidebar YAML</Typography>
      <Typography variant="body1">
        Configure your landing page sidebar, wiki-page list, and custom navigation links.
        This file is private to your account.
      </Typography>
      <TextField
        className={classes.editor}
        label="user-sidebar.yaml"
        value={value}
        onChange={event => setValue(event.target.value)}
        variant="outlined"
        fullWidth
        multiline
        rowsMin={20}
      />
      <Box className={classes.actions}>
        <Typography color="textSecondary">{status}</Typography>
        <Button color="primary" variant="contained" onClick={handleSave} disabled={saving || loading}>
          Save YAML
        </Button>
      </Box>
    </Paper>
  </Page>
}
