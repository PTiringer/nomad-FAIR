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
import { makeStyles } from '@material-ui/core'
import Markdown from './Markdown'
import { appBase } from '../config'

const useStyles = makeStyles(theme => ({
  root: {
    padding: theme.spacing(3),
    maxWidth: 1024,
    margin: 'auto',
    width: '100%'
  }
}))

export default function Docs() {
  const classes = useStyles()

  return (
    <div className={classes.root}>
      <Markdown>{`
      # Documentation

      This distribution has been trimmed down to keep only the apps you use. The original
      static docs bundle is not part of this setup anymore, so this page collects the
      relevant documentation links in one place.

      ## NOMAD documentation

      - [Public NOMAD documentation](https://nomad-lab.eu/prod/v1/docs/index.html)
      - [API dashboard](${appBase}/api/v1/extensions/docs)
      - [About this distribution](./information)
      - [Frequently asked questions](./faq)

      ## Installed app docs

      - ELN Basic: use the standard NOMAD guides above
      - WikiPage plugin docs live in the repository under \`packages/wiki-page/docs\`
    `}</Markdown>
    </div>
  )
}
