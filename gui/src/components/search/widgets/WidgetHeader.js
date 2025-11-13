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
import React, { useState, useCallback } from 'react'
import { IconButton, makeStyles } from '@material-ui/core'
import { Cancel, InfoOutlined } from '@material-ui/icons'
import PropTypes from 'prop-types'
import clsx from 'clsx'
import { useSearchContext } from '../SearchContext'
import FilterTitle from '../FilterTitle'
import { Actions, ActionHeader, Action } from '../../Actions'
import { HelpDialog } from '../../Help'

/**
 * The header displayed by all widgets.
 */
const useStyles = makeStyles(theme => ({
  root: {
    marginBottom: theme.spacing(0.5),
    height: '2.5rem',
    width: '100%'
  },
  handle: {
    display: 'flex',
    height: '100%',
    alignItems: 'center',
    flexGrow: 1,
    minWidth: 0,
    cursor: 'grabbing'
  },
  spacer: {
    flexGrow: 1,
    minWidth: 0
  }
}))
const WidgetHeader = React.memo(({
  id,
  quantity,
  label,
  description,
  disableUnit,
  actions,
  className,
  classes
}) => {
  const styles = useStyles({classes: classes})
  const { useRemoveWidget } = useSearchContext()
  const removeWidget = useRemoveWidget()
  const [open, setOpen] = useState(false)

  const handleRemove = useCallback(() => {
    removeWidget(id)
  }, [removeWidget, id])

  const handleToggleDialog = useCallback(() => {
    setOpen(old => !old)
  }, [])

  return <Actions className={clsx(styles.root, className)}>
    <ActionHeader disableSpacer>
      <div
        className={clsx("dragHandle", styles.handle)}
      >
        <FilterTitle
          variant="subtitle2"
          quantity={quantity}
          label={label}
          disableUnit={disableUnit}
          TooltipProps={{open: false}}
          full
        />
        {description && <IconButton size="small" onClick={handleToggleDialog}>
          <InfoOutlined style={{fontSize: 16}}/>
        </IconButton>}
        <div className={styles.spacer}/>
      </div>
    </ActionHeader>
    {actions}
    <Action tooltip='Remove' onClick={handleRemove} data-testid={`${id}-remove-widget`}>
      <Cancel fontSize="small"/>
    </Action>
    {description && <HelpDialog heading={label} text={description} open={open} onClose={handleToggleDialog}/>}
  </Actions>
})

WidgetHeader.propTypes = {
  id: PropTypes.string.isRequired,
  quantity: PropTypes.string,
  label: PropTypes.string,
  description: PropTypes.string,
  disableUnit: PropTypes.bool,
  variant: PropTypes.string,
  actions: PropTypes.node,
  className: PropTypes.string,
  classes: PropTypes.object
}

export default WidgetHeader
