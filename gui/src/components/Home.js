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
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import PropTypes from 'prop-types'
import { Link as RouterLink, useHistory } from 'react-router-dom'
import {
  Box,
  Button,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListSubheader,
  Paper,
  Typography,
  makeStyles
} from '@material-ui/core'
import ArrowBackIcon from '@material-ui/icons/ArrowBack'
import YAML from 'yaml'
import About from './About'
import Markdown from './Markdown'
import Page from './Page'
import { DoesNotExist, useApi } from './api'
import { useErrors } from './errors'
import { formatTimestamp } from '../utils'
import { Action } from './Actions'
import { Menu, MenuContent, MenuHeader } from './search/menus/Menu'

const defaultLandingPage = {
  widgets: [
    {
      type: 'hero',
      title: 'Welcome back, {{displayName}}',
      text: 'Here are your 10 most recent projects. Open one directly, or go to the full projects page to manage everything.',
      actions: [
        {
          label: 'Open all projects',
          to: '/user/uploads',
          variant: 'contained'
        }
      ]
    },
    {
      type: 'recent_uploads',
      title: 'Recent projects',
      limit: 10,
      empty_text: 'You do not have any projects yet.',
      empty_action: {
        label: 'Go to projects',
        to: '/user/uploads'
      }
    }
  ]
}

const defaultSidebar = {
  title: 'My wiki pages',
  wiki_pages: {
    enabled: true,
    title: 'Wiki pages',
    limit: 20,
    empty_text: 'You do not have any wiki pages yet.'
  },
  links: []
}

const wikiPageSchema = 'wiki_page.schema_packages.schema_package.WikiPage'

const scientificStaffSchema = (
  'mpi_cbs_scientific_staff_database.schema_packages.schema_package.' +
  'ScientificStaffProfile'
)

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
  toolbarButton: {
    marginLeft: theme.spacing(1)
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginBottom: theme.spacing(2)
  },
  layout: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: theme.spacing(3),
    [theme.breakpoints.down('sm')]: {
      flexDirection: 'column'
    }
  },
  sidebar: {
    flexShrink: 0,
    height: 'calc(100vh - 190px)',
    minHeight: 400,
    position: 'sticky',
    top: theme.spacing(2),
    zIndex: 2,
    [theme.breakpoints.down('sm')]: {
      width: '100%',
      height: 360,
      minHeight: 360,
      position: 'relative',
      top: 0
    }
  },
  sidebarActions: {
    padding: theme.spacing(1, 1.5, 2)
  },
  content: {
    flex: '1 1 auto',
    minWidth: 0
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

function getProfileDisplayName(user, displayName) {
  return user?.name || user?.preferred_username || user?.email || displayName || 'New profile'
}

function getEntryPath(uploadId, entryId) {
  return `/user/uploads/upload/id/${uploadId}/entry/id/${entryId}/data/data`
}

function ScientificStaffProfileButton({action, values, className}) {
  const { api, user } = useApi()
  const { raiseError } = useErrors()
  const history = useHistory()
  const [clicked, setClicked] = useState(false)

  const handleClick = useCallback(async () => {
    if (clicked) return

    if (!user) {
      history.push('/user/uploads')
      return
    }

    setClicked(true)

    try {
      const existingProfiles = await api.post('entries/query', {
        owner: 'user',
        query: {
          'section_defs.definition_qualified_name': scientificStaffSchema
        },
        pagination: {
          page_size: 1,
          order_by: 'upload_create_time',
          order: 'desc'
        },
        required: {
          include: ['upload_id', 'entry_id']
        }
      })
      const existingProfile = existingProfiles?.data?.[0]

      if (existingProfile?.upload_id && existingProfile?.entry_id) {
        history.push(getEntryPath(existingProfile.upload_id, existingProfile.entry_id))
        return
      }

      const archive = {
        data: {
          m_def: scientificStaffSchema,
          display_name: getProfileDisplayName(user, values.displayName),
          email: user?.email || '',
          last_updated: new Date().toISOString()
        }
      }
      const upload = await api.post('/uploads')
      const response = await api.put(
        `uploads/${upload.upload_id}/raw/?file_name=scientific-staff-profile.archive.json&overwrite_if_exists=false&wait_for_processing=true`,
        archive
      )

      const entryId = response?.processing?.entry_id
      if (!entryId) {
        throw new Error('Failed to create the scientific staff profile entry.')
      }

      history.push(getEntryPath(upload.upload_id, entryId))
    } catch (error) {
      setClicked(false)
      raiseError(error)
    }
  }, [api, clicked, history, raiseError, user, values.displayName])

  return <Button
    className={className}
    color={action.color || 'primary'}
    disabled={clicked}
    onClick={handleClick}
    variant={action.variant || 'outlined'}
  >
    {interpolate(action.label || 'Scientific Staff Profile', values)}
  </Button>
}
ScientificStaffProfileButton.propTypes = {
  action: PropTypes.object,
  values: PropTypes.object.isRequired,
  className: PropTypes.string
}

function ActionButton({action, values, className}) {
  if (!action?.label) return null
  if (action.type === 'scientific_staff_profile') {
    return <ScientificStaffProfileButton action={action} values={values} className={className} />
  }
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
  const [sidebarConfig, setSidebarConfig] = useState(null)
  const [sidebarLoaded, setSidebarLoaded] = useState(false)
  const [wikiPages, setWikiPages] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

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

  useEffect(() => {
    if (!api?.keycloak?.authenticated) {
      setSidebarConfig(null)
      setSidebarLoaded(false)
      return
    }

    api.get('users/me/sidebar')
      .then(text => setSidebarConfig(text ? YAML.parse(text) : null))
      .catch(error => {
        if (!(error instanceof DoesNotExist)) errors.raiseError(error)
        setSidebarConfig(null)
      })
      .finally(() => setSidebarLoaded(true))
  }, [api, errors])

  const landingPage = useMemo(() => getLandingPage(landingPageConfig, user), [landingPageConfig, user])
  const widgets = Array.isArray(landingPage?.widgets) ? landingPage.widgets : defaultLandingPage.widgets
  const sidebar = sidebarConfig || defaultSidebar
  const wikiConfig = sidebar?.wiki_pages || {}
  const wikiEnabled = wikiConfig.enabled !== false
  const wikiLimit = wikiConfig.limit || 20
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

  useEffect(() => {
    if (!api?.keycloak?.authenticated || !sidebarLoaded || !wikiEnabled) {
      setWikiPages([])
      return
    }

    api.post('entries/query', {
      owner: 'user',
      query: {'section_defs.definition_qualified_name': wikiPageSchema},
      pagination: {
        page_size: wikiLimit,
        order_by: 'upload_create_time',
        order: 'desc'
      },
      required: {
        include: ['upload_id', 'entry_id', 'entry_name', 'upload_create_time']
      }
    })
      .then(response => setWikiPages(response?.data || []))
      .catch(error => {
        setWikiPages([])
        errors.raiseError(error)
      })
  }, [api, errors, sidebarLoaded, wikiEnabled, wikiLimit])

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

  const loading = !configLoaded || !sidebarLoaded || Boolean(uploadLimit && !uploads) ||
    Boolean(wikiEnabled && !wikiPages)

  return <Page limitedWidth loading={loading}>
    <Box className={classes.toolbar}>
      <ScientificStaffProfileButton
        action={{label: 'Scientific Staff Profile', variant: 'outlined'}}
        values={values}
        className={classes.toolbarButton}
      />
      <Button
        className={classes.toolbarButton}
        color="primary"
        variant="outlined"
        component={RouterLink}
        to="/user/landing-page"
      >
        Edit landing page
      </Button>
    </Box>
    <Box className={classes.layout}>
      <aside className={classes.sidebar}>
        <Menu
          size="sm"
          open
          collapsed={sidebarCollapsed}
          onCollapsedChanged={setSidebarCollapsed}
          visible
        >
          <MenuHeader
            title={interpolate(sidebar.title || 'My sidebar', values)}
            actions={<Action tooltip="Collapse menu" onClick={() => setSidebarCollapsed(true)}>
              <ArrowBackIcon fontSize="small" />
            </Action>}
          />
          <MenuContent collapsedTitle={interpolate(sidebar.title || 'My sidebar', values)}>
            {wikiEnabled && <React.Fragment>
              <ListSubheader disableSticky>
                {interpolate(wikiConfig.title || 'Wiki pages', values)}
              </ListSubheader>
              {(wikiPages || []).map(page => <ListItem
                button
                key={page.entry_id}
                component={RouterLink}
                to={getEntryPath(page.upload_id, page.entry_id)}
              >
                <ListItemText primary={page.entry_name || page.entry_id} />
              </ListItem>)}
              {(wikiPages || []).length === 0 && <ListItem>
                <ListItemText secondary={interpolate(
                  wikiConfig.empty_text || 'You do not have any wiki pages yet.', values
                )} />
              </ListItem>}
            </React.Fragment>}
            {Array.isArray(sidebar.links) && sidebar.links.length > 0 && <React.Fragment>
              <Divider />
              <ListSubheader disableSticky>Links</ListSubheader>
              {sidebar.links.filter(link => link?.label).map((link, index) => <ListItem
                button
                key={index}
                component={link.href ? 'a' : RouterLink}
                href={link.href ? interpolate(link.href, values) : undefined}
                to={link.href ? undefined : interpolate(link.to || '/', values)}
              >
                <ListItemText primary={interpolate(link.label, values)} />
              </ListItem>)}
            </React.Fragment>}
            <Box className={classes.sidebarActions}>
              <Button component={RouterLink} to="/user/sidebar" color="primary" size="small">
                Edit sidebar YAML
              </Button>
            </Box>
          </MenuContent>
        </Menu>
      </aside>
      <Box className={classes.content}>
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
            {interpolate(widget.title || 'Recent projects', values)}
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
            {interpolate(widget.empty_text || 'You do not have any projects yet.', values)}
          </Typography>
          <ActionButton
            action={widget.empty_action || {label: 'Go to projects', to: '/user/uploads'}}
            values={values}
          />
        </Box>}
      </Paper>
    })}
      </Box>
    </Box>
  </Page>
}
