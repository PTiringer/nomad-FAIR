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
import { cloneDeep } from 'lodash'
import { Link as RouterLink } from 'react-router-dom'
import {
  Box,
  Button,
  Divider,
  Icon,
  List,
  ListItemIcon,
  ListItem,
  ListItemText,
  Paper,
  Typography,
  makeStyles
} from '@material-ui/core'
import ArrowBackIcon from '@material-ui/icons/ArrowBack'
import DOMPurify from 'dompurify'
import YAML from 'yaml'
import About from './About'
import { Action } from './Actions'
import Markdown from './Markdown'
import Page from './Page'
import { DoesNotExist, useApi } from './api'
import RichTextEditQuantity from './editQuantity/RichTextEditQuantity'
import { useErrors } from './errors'
import {
  Menu,
  MenuContent,
  MenuHeader
} from './search/menus/Menu'
import { formatTimestamp } from '../utils'

const defaultLandingPage = {
  sidebar: {
    title: 'Workspace',
    items: [
      {
        type: 'link',
        label: 'Uploads',
        to: '/user/uploads',
        icon: 'cloud_upload'
      },
      {
        type: 'link',
        label: 'Datasets',
        to: '/user/datasets',
        icon: 'storage'
      },
      {
        type: 'link',
        label: 'Search your data',
        to: '/user/search',
        icon: 'search'
      },
      {
        type: 'divider'
      },
      {
        type: 'markdown',
        text: 'Add personal links and notes here from the same YAML file.'
      }
    ]
  },
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
    },
    {
      type: 'markdown',
      text: 'Use this space to add a short personal note, links, or instructions for your landing page.'
    },
    {
      type: 'notes',
      title: 'Notes',
      content: '<p>Use this rich-text area to keep personal notes, highlight links, or add formatted instructions for your landing page.</p>'
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
  notesActions: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: theme.spacing(2),
    gap: theme.spacing(2)
  },
  toolbar: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginBottom: theme.spacing(2)
  },
  landingRoot: {
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'stretch',
    minHeight: 'calc(100vh - 112px)'
  },
  landingContent: {
    flexGrow: 1,
    minWidth: 0,
    maxWidth: 1024 + theme.spacing(2),
    paddingLeft: theme.spacing(2),
    paddingRight: theme.spacing(2),
    marginLeft: 'auto',
    marginRight: 'auto'
  },
  landingSidebarColumn: {
    flexShrink: 0,
    zIndex: 2
  },
  sidebarItem: {
    paddingTop: theme.spacing(0.75),
    paddingBottom: theme.spacing(0.75)
  },
  sidebarIcon: {
    minWidth: '2rem'
  },
  sidebarMarkdown: {
    padding: theme.spacing(2),
    color: theme.palette.text.secondary
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

function updateLandingPage(config, user, updatePage) {
  const source = cloneDeep(config || defaultLandingPage)
  const keys = getUserKeys(user)

  for (const key of keys) {
    if (source?.users?.[key]) {
      source.users[key] = updatePage(Array.isArray(source.users[key]) ? {widgets: source.users[key]} : source.users[key])
      return source
    }
  }

  if (source?.default !== undefined) {
    source.default = updatePage(Array.isArray(source.default) ? {widgets: source.default} : source.default)
    return source
  }

  return updatePage(Array.isArray(source) ? {widgets: source} : source)
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

function isExternalLink(value) {
  return typeof value === 'string' && /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(value)
}

function getSidebarLinkProps(item, values) {
  const href = interpolate(item.href || item.url, values)
  if (href) {
    return {
      button: true,
      component: 'a',
      href,
      target: item.target,
      rel: item.target === '_blank' ? 'noopener noreferrer' : undefined
    }
  }

  const to = interpolate(item.to || item.route || item.path || '/', values)
  if (isExternalLink(to)) {
    return {
      button: true,
      component: 'a',
      href: to,
      target: item.target,
      rel: item.target === '_blank' ? 'noopener noreferrer' : undefined
    }
  }

  return {
    button: true,
    component: RouterLink,
    to
  }
}

function LandingSidebar({sidebar, values, collapsed, onCollapsedChange}) {
  const classes = useStyles()
  const title = interpolate(sidebar?.title || 'Menu', values)
  const items = sidebar?.items || []

  return <Menu
    size={sidebar?.size || sidebar?.width}
    open={true}
    collapsed={collapsed}
    onCollapsedChanged={onCollapsedChange}
    visible={true}
  >
    <MenuHeader
      title={title}
      actions={<Action
        tooltip="Collapse menu"
        onClick={() => onCollapsedChange(true)}
      >
        <ArrowBackIcon fontSize="small" />
      </Action>}
    />
    <MenuContent collapsedTitle={title}>
      {items.map((item, index) => {
        if (item?.visible === false) return null
        if (item?.type === 'divider') return <Divider key={index} />
        if (item?.type === 'markdown') {
          return <Box key={index} className={classes.sidebarMarkdown}>
            <Markdown text={interpolate(item.text || '', values)} />
          </Box>
        }
        if (item?.type === 'text') {
          return <Box key={index} className={classes.sidebarMarkdown}>
            <Typography variant={item.variant || 'body2'}>
              {interpolate(item.text || '', values)}
            </Typography>
          </Box>
        }

        const label = interpolate(item?.label || item?.title || '', values)
        if (!label) return null
        const listItemProps = getSidebarLinkProps(item, values)
        return <ListItem key={index} className={classes.sidebarItem} {...listItemProps}>
          {item.icon && <ListItemIcon className={classes.sidebarIcon}>
            <Icon fontSize="small">{item.icon}</Icon>
          </ListItemIcon>}
          <ListItemText
            primary={label}
            secondary={item.description ? interpolate(item.description, values) : undefined}
          />
        </ListItem>
      })}
    </MenuContent>
  </Menu>
}
LandingSidebar.propTypes = {
  sidebar: PropTypes.object,
  values: PropTypes.object.isRequired,
  collapsed: PropTypes.bool,
  onCollapsedChange: PropTypes.func.isRequired
}

export default function Home() {
  const classes = useStyles()
  const { api, user } = useApi()
  const errors = useErrors()
  const [uploads, setUploads] = useState(null)
  const [landingPageConfig, setLandingPageConfig] = useState(null)
  const [configLoaded, setConfigLoaded] = useState(false)
  const [notesDirty, setNotesDirty] = useState({})
  const [notesSaving, setNotesSaving] = useState({})
  const [notesStatus, setNotesStatus] = useState({})
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

  const landingPage = useMemo(() => getLandingPage(landingPageConfig, user), [landingPageConfig, user])
  const widgets = Array.isArray(landingPage?.widgets) ? landingPage.widgets : defaultLandingPage.widgets
  const sidebar = landingPage?.sidebar
  const showSidebar = sidebar?.enabled !== false && Array.isArray(sidebar?.items) && sidebar.items.length > 0
  const uploadLimit = useMemo(() => {
    return widgets
      .filter(widget => widget?.type === 'recent_uploads')
      .reduce((limit, widget) => Math.max(limit, widget.limit || 10), 0)
  }, [widgets])

  useEffect(() => {
    setSidebarCollapsed(Boolean(sidebar?.collapsed))
  }, [sidebar?.collapsed])

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

  const handleNotesChange = (widgetIndex, content) => {
    setLandingPageConfig(prev => updateLandingPage(prev, user, (page) => {
      const widgets = Array.isArray(page?.widgets) ? [...page.widgets] : []
      const currentWidget = widgets[widgetIndex] || {}
      widgets[widgetIndex] = {
        ...currentWidget,
        content: content || ''
      }
      return {...page, widgets}
    }))
    setNotesDirty(prev => ({...prev, [widgetIndex]: true}))
    setNotesStatus(prev => ({...prev, [widgetIndex]: ''}))
  }

  const handleNotesSave = (widgetIndex) => {
    const body = YAML.stringify(landingPageConfig || defaultLandingPage)
    setNotesSaving(prev => ({...prev, [widgetIndex]: true}))
    setNotesStatus(prev => ({...prev, [widgetIndex]: ''}))
    api.put('users/me/landing-page', body, {
      headers: {
        'Content-Type': 'application/yaml',
        accept: 'application/yaml'
      }
    })
      .then(() => {
        setNotesDirty(prev => ({...prev, [widgetIndex]: false}))
        setNotesStatus(prev => ({...prev, [widgetIndex]: 'Saved.'}))
      })
      .catch(errors.raiseError)
      .finally(() => {
        setNotesSaving(prev => ({...prev, [widgetIndex]: false}))
      })
  }

  const content = <>
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

      if (widget.type === 'notes') {
        return <Paper key={widgetIndex} className={`${classes.markdown} ${classes.widget}`}>
          {widget.title && <Typography variant="h5" gutterBottom>
            {interpolate(widget.title, values)}
          </Typography>}
          <RichTextEditQuantity
            quantityDef={{name: 'notes', label: interpolate(widget.title || 'Notes', values)}}
            value={DOMPurify.sanitize(widget.content || '')}
            onChange={(content) => handleNotesChange(widgetIndex, content)}
            height={360}
          />
          <Box className={classes.notesActions}>
            <Typography color="textSecondary">
              {notesStatus[widgetIndex] || (notesDirty[widgetIndex] ? 'Unsaved changes.' : '')}
            </Typography>
            <Button
              color="primary"
              variant="contained"
              onClick={() => handleNotesSave(widgetIndex)}
              disabled={!notesDirty[widgetIndex] || notesSaving[widgetIndex]}
            >
              Save notes
            </Button>
          </Box>
        </Paper>
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
  </>

  const loading = !configLoaded || Boolean(uploadLimit && !uploads)
  if (!showSidebar) {
    return <Page limitedWidth loading={loading}>{content}</Page>
  }

  return <Page loading={loading} style={{marginLeft: 0, marginRight: 0}}>
    <Box className={classes.landingRoot}>
      <Box className={classes.landingSidebarColumn}>
        <LandingSidebar
          sidebar={sidebar}
          values={values}
          collapsed={sidebarCollapsed}
          onCollapsedChange={setSidebarCollapsed}
        />
      </Box>
      <Box className={classes.landingContent}>
        {content}
      </Box>
    </Box>
  </Page>
}
