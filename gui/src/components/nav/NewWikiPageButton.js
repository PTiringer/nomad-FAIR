import React, { useCallback, useState } from 'react'
import { Button, makeStyles } from '@material-ui/core'
import { useHistory } from 'react-router-dom'
import { useApi } from '../api'
import { useErrors } from '../errors'

const useStyles = makeStyles(theme => ({
  root: {
    marginLeft: theme.spacing(1),
    whiteSpace: 'nowrap'
  }
}))

function formatWikiPageName(user, now = new Date()) {
  const authorName = user?.name || user?.preferred_username || user?.sub || 'Unknown author'
  const year = now.getFullYear()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  const hours = `${now.getHours()}`.padStart(2, '0')
  const minutes = `${now.getMinutes()}`.padStart(2, '0')

  return `${year}-${month}-${day} ${hours}:${minutes} ${authorName}`
}

const NewWikiPageButton = React.memo(() => {
  const classes = useStyles()
  const { api, user } = useApi()
  const { raiseError } = useErrors()
  const history = useHistory()
  const [clicked, setClicked] = useState(false)

  const handleClick = useCallback(async () => {
    if (clicked) {
      return
    }

    if (!user) {
      history.push('/user/uploads')
      return
    }

    setClicked(true)

    try {
      const wikiPageArchive = {
        data: {
          m_def: 'wiki_page.schema_packages.schema_package.WikiPage',
          name: formatWikiPageName(user),
          tags: ['wiki', 'knowledge-base']
        }
      }
      const upload = await api.post('/uploads')
      const response = await api.put(
        `uploads/${upload.upload_id}/raw/?file_name=home.archive.json&overwrite_if_exists=false&wait_for_processing=true`,
        wikiPageArchive
      )

      const entryId = response?.processing?.entry_id
      if (!entryId) {
        throw new Error('Failed to create the wiki page entry.')
      }

      history.push(`/user/uploads/upload/id/${upload.upload_id}/entry/id/${entryId}`)
    } catch (error) {
      setClicked(false)
      raiseError(error)
    }
  }, [api, clicked, history, raiseError, user])

  return (
    <Button
      className={classes.root}
      color="primary"
      disabled={clicked}
      onClick={handleClick}
      size="small"
    >
      New Wiki Page
    </Button>
  )
})

export default NewWikiPageButton
