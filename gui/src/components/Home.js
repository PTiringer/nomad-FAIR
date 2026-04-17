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
import React, { useEffect, useMemo, useState } from 'react'
import PropTypes from 'prop-types'
import { Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Button,
  Divider,
  List,
  ListItem,
  ListItemText,
  Paper,
  Typography,
  makeStyles
} from '@material-ui/core'
import YAML from 'yaml'
import About from './About'
import Markdown from './Markdown'
import Page from './Page'
import { DoesNotExist, useApi } from './api'
import { useErrors } from './errors'
import { formatTimestamp } from '../utils'

const defaultLandingPage = {
  widgets: [
    {
      type: 'hero',
      title: 'Welcome back, {{displayName}}',
      text: 'Here are your 10 most recent uploads. Open one directly, or go to the full uploads page to manage everything.',
      actions: [
        {
          label: 'Open all uploads',
          to: '/user/uploads',
          variant: 'contained'
        }
      ]
    },
    {
      type: 'recent_uploads',
      title: 'Recent uploads',
      limit: 10,
      empty_text: 'You do not have any uploads yet.',
      empty_action: {
        label: 'Go to uploads',
        to: '/user/uploads'
      }
    }
  ]
}

const useStyles = makeStyles(theme => ({
  hero: {
    padding: theme.spacing(4),
    marginBottom: theme.spacing(3)
  },
  uploadsCard: {
    overflow: 'hidden'
  },
  uploadMeta: {
    color: theme.palette.text.secondary
  },
  emptyState: {
    padding: theme.spacing(4)
  },
  widget: {
    marginBottom: theme.spacing(3)
  },
  markdown: {
    padding: theme.spacing(3)
  },
  action: {
    marginTop: theme.spacing(2),
    marginRight: theme.spacing(1)
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginBottom: theme.spacing(2)
  }
}))

function getUserKeys(user) {
  return [
    user?.sub,
    user?.user_id,
    user?.id,
    user?.preferred_username,
    user?.username,
    user?.email,
    user?.name
  ].filter(Boolean)
}

function getLandingPage(config, user) {
  const source = config || defaultLandingPage
  const userConfig = getUserKeys(user)
    .map(key => source?.users?.[key])
    .find(Boolean)
  const page = userConfig || source?.default || source
  return Array.isArray(page) ? {widgets: page} : page
}

function interpolate(value, values) {
  if (typeof value !== 'string') return value
  return value.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, key) => {
    return values[key] || ''
  })
}

function ActionButton({action, values, className}) {
  if (!action?.label) return null
  const props = {
    className,
    color: action.color || 'primary',
    variant: action.variant || 'outlined'
  }
  const label = interpolate(action.label, values)
  if (action.href) {
    return <Button {...props} href={interpolate(action.href, values)}>
      {label}
    </Button>
  }
  return <Button {...props} component={RouterLink} to={interpolate(action.to || '/user/uploads', values)}>
    {label}
  </Button>
}
ActionButton.propTypes = {
  action: PropTypes.object,
  values: PropTypes.object.isRequired,
  className: PropTypes.string
}

export default function Home() {
  const classes = useStyles()
  const { api, user } = useApi()
  const errors = useErrors()
  const [uploads, setUploads] = useState(null)
  const [landingPageConfig, setLandingPageConfig] = useState(null)
  const [configLoaded, setConfigLoaded] = useState(false)

  useEffect(() => {
    if (!api?.keycloak?.authenticated) {
      setLandingPageConfig(null)
      setConfigLoaded(false)
      return
    }

    api.get('users/me/landing-page')
      .then(text => {
        setLandingPageConfig(text ? YAML.parse(text) : null)
        setConfigLoaded(true)
      })
      .catch(error => {
        if (error instanceof DoesNotExist) {
          setLandingPageConfig(null)
          setConfigLoaded(true)
          return
        }
        setLandingPageConfig(null)
        setConfigLoaded(true)
        errors.raiseError(error)
      })
  }, [api, errors])

  const landingPage = useMemo(() => getLandingPage(landingPageConfig, user), [landingPageConfig, user])
  const widgets = Array.isArray(landingPage?.widgets) ? landingPage.widgets : defaultLandingPage.widgets
  const uploadLimit = useMemo(() => {
    return widgets
      .filter(widget => widget?.type === 'recent_uploads')
      .reduce((limit, widget) => Math.max(limit, widget.limit || 10), 0)
  }, [widgets])

  useEffect(() => {
    if (!api?.keycloak?.authenticated || !uploadLimit) {
      setUploads(null)
      return
    }

    api.get(`/uploads?page_size=${uploadLimit}&page=1&order_by=upload_create_time&order=desc`)
      .then(setUploads)
      .catch(errors.raiseError)
  }, [api, errors, uploadLimit])

  if (!api?.keycloak?.authenticated) {
    return <About />
  }

  const recentUploads = uploads?.data || []
  const displayName = user?.firstName || user?.given_name || user?.name || 'there'
  const values = {
    displayName,
    name: user?.name || displayName,
    username: user?.preferred_username || user?.username || '',
    email: user?.email || ''
  }

  return <Page limitedWidth loading={!configLoaded || Boolean(uploadLimit && !uploads)}>
    <Box className={classes.toolbar}>
      <Button
        color="primary"
        variant="outlined"
        component={RouterLink}
        to="/user/landing-page"
      >
        Edit landing page
      </Button>
    </Box>
    {widgets.map((widget, widgetIndex) => {
      if (widget.type === 'hero') {
        return <Paper key={widgetIndex} className={`${classes.hero} ${classes.widget}`}>
          <Typography variant={widget.title_variant || 'h4'} gutterBottom>
            {interpolate(widget.title, values)}
          </Typography>
          {widget.text && <Typography variant="body1" paragraph>
            {interpolate(widget.text, values)}
          </Typography>}
          {widget.actions?.map((action, actionIndex) => (
            <ActionButton
              key={actionIndex}
              action={action}
              values={values}
              className={classes.action}
            />
          ))}
        </Paper>
      }

      if (widget.type === 'markdown') {
        return <Paper key={widgetIndex} className={`${classes.markdown} ${classes.widget}`}>
          <Markdown text={interpolate(widget.text || '', values)} />
        </Paper>
      }

      if (widget.type === 'button') {
        return <Box key={widgetIndex} className={classes.widget}>
          <ActionButton action={widget} values={values} />
        </Box>
      }

      if (widget.type !== 'recent_uploads') {
        return null
      }

      const limit = widget.limit || 10
      const uploadsToShow = recentUploads.slice(0, limit)
      return <Paper key={widgetIndex} className={`${classes.uploadsCard} ${classes.widget}`}>
        <Box p={3}>
          <Typography variant="h5">
            {interpolate(widget.title || 'Recent uploads', values)}
          </Typography>
        </Box>
        <Divider />
        {uploadsToShow.length > 0 && <List disablePadding>
          {uploadsToShow.map((upload, index) => (
            <React.Fragment key={upload.upload_id}>
              <ListItem
                button
                component={RouterLink}
                to={`/user/uploads/upload/id/${upload.upload_id}`}
              >
                <ListItemText
                  primary={upload.upload_name || upload.upload_id}
                  secondary={
                    <React.Fragment>
                      <span className={classes.uploadMeta}>
                        Created {formatTimestamp(upload.upload_create_time)}
                      </span>
                      {upload.upload_name && <span className={classes.uploadMeta}>
                        {' '}| {upload.upload_id}
                      </span>}
                    </React.Fragment>
                  }
                />
              </ListItem>
              {index < uploadsToShow.length - 1 && <Divider component="li" />}
            </React.Fragment>
          ))}
        </List>}
        {uploadsToShow.length === 0 && <Box className={classes.emptyState}>
          <Typography variant="body1" paragraph>
            {interpolate(widget.empty_text || 'You do not have any uploads yet.', values)}
          </Typography>
          <ActionButton
            action={widget.empty_action || {label: 'Go to uploads', to: '/user/uploads'}}
            values={values}
          />
        </Box>}
      </Paper>
    })}
  </Page>
}
