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
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Editor } from '@tinymce/tinymce-react'
import PropTypes from 'prop-types'
import {
  Box,
  FormControl,
  FormLabel,
  makeStyles
} from '@material-ui/core'
import Dialog from '@material-ui/core/Dialog'
import AppBar from '@material-ui/core/AppBar'
import Toolbar from '@material-ui/core/Toolbar'
import IconButton from '@material-ui/core/IconButton'
import Typography from '@material-ui/core/Typography'
import DOMPurify from 'dompurify'
import { getDisplayLabel } from '../../utils'
import { useRecoilValue } from 'recoil'
import { configState } from '../archive/ArchiveBrowser'

const CloseIcon = () => <>✕</>
const OpenInFullIcon = () => <>⛶</>

const useStyle = makeStyles(theme => ({
  root: {
    borderBottom: '1px solid rgba(0, 0, 0, 0.42)',
    marginBottom: 1
  },
  focused: {
    transition: 'border-bottom-color 200ms cubic-bezier(0.4, 0, 0.2, 1) 0ms',
    transitionProperty: 'border-bottom-color',
    transitionDuration: '200ms',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDelay: '0ms',
    borderBottom: `2px solid ${theme.palette.primary.main}`
  }
}))

const RichTextEditQuantity = React.memo((props) => {
  const classes = useStyle()
  const { quantityDef, value, onChange, height } = props
  const config = useRecoilValue(configState)
  const label = getDisplayLabel(quantityDef, true, config?.showMeta)

  const editedValue = useRef(value || '')
  const [focus, setFocus] = useState(false)
  const [initialized, setInitialized] = useState(false)
  const [open, setOpen] = useState(false)
  const tinymceBasePath = `${process.env.PUBLIC_URL || ''}/tinymce`

  // Responsive editor height:
  // - use provided `height` prop if present
  // - otherwise use 60% of viewport height
  const [editorHeight, setEditorHeight] = useState(() => {
    if (height) return height
    if (typeof window !== 'undefined') {
      return Math.round(window.innerHeight * 0.6)
    }
    return 500
  })

  // Single source of truth for content
  const [content, setContent] = useState(value || '')

  useEffect(() => {
    const v = value || ''
    editedValue.current = v
    setContent(v)
  }, [value])

  useEffect(() => {
    if (height) {
      setEditorHeight(height)
      return
    }

    const handleResize = () => {
      setEditorHeight(Math.round(window.innerHeight * 0.6))
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [height])

  const handleChange = useCallback((newValue) => {
    const v = newValue || ''
    editedValue.current = v
    setContent(v)
    if (onChange) {
      onChange(v === '' ? undefined : v)
    }
  }, [onChange])

  const handleImageUpload = useCallback((blobInfo, success, failure, progress) => {
    success('data:' + blobInfo.blob().type + ';base64,' + blobInfo.base64())
  }, [])

  const handleEditorInit = useCallback(() => {
    setInitialized(true)
  }, [])

  const editorInit = useMemo(() => ({
    resize: true,
    height: editorHeight,
    menubar: false,
    plugins: [
      'advlist autolink lists link image charmap print preview anchor',
      'searchreplace visualblocks code',
      'insertdatetime media table paste code help wordcount'
    ],
    toolbar: 'undo redo | formatselect | ' +
      'bold italic backcolor link editimage | alignleft aligncenter ' +
      'alignright alignjustify | bullist numlist outdent indent | image table | ' +
      'removeformat',
    default_link_target: "_blank",
    link_title: true,
    skin: 'nomad',
    content_css: 'default',
    images_upload_handler: handleImageUpload,
    paste_data_images: true,
    base_url: tinymceBasePath,
    suffix: '.min'
  }), [editorHeight, handleImageUpload, tinymceBasePath])

  return (
    <FormControl
      fullWidth
      focused={focus}
      className={focus ? classes.focused : classes.root}
    >
      <Box marginY={1} display="flex" alignItems="center" justifyContent="space-between">
        <FormLabel>{label}</FormLabel>
        <IconButton
          size="small"
          onClick={() => setOpen(true)}
          aria-label="Open editor in fullscreen"
        >
          <OpenInFullIcon />
        </IconButton>
      </Box>

      <Box height={initialized ? 'initial' : editorHeight}>
        <Editor
          onInit={handleEditorInit}
          init={editorInit}
          value={DOMPurify.sanitize(content)}
          onEditorChange={handleChange}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
        />
      </Box>

      <Dialog fullScreen open={open} onClose={() => setOpen(false)}>
        <AppBar position="static">
          <Toolbar>
            <IconButton
              edge="start"
              color="inherit"
              onClick={() => setOpen(false)}
              aria-label="Close"
            >
              <CloseIcon />
            </IconButton>
            <Typography variant="h6" style={{ marginLeft: 12, flex: 1 }}>
              {label}
            </Typography>
          </Toolbar>
        </AppBar>

        <Box p={2} height="calc(100vh - 64px)">
          <Editor
            init={{ ...editorInit, height: '100%' }}
            value={DOMPurify.sanitize(content)}
            onEditorChange={handleChange}
          />
        </Box>
      </Dialog>
    </FormControl>
  )
})

RichTextEditQuantity.propTypes = {
  quantityDef: PropTypes.object.isRequired,
  value: PropTypes.string,
  onChange: PropTypes.func,
  height: PropTypes.oneOfType([PropTypes.number, PropTypes.string])
}

export default RichTextEditQuantity
