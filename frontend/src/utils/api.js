export function getCsrfToken() {
  const match = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
  return match ? decodeURIComponent(match.split('=')[1]) : ''
}

export async function ensureSession() {
  const response = await fetch('http://localhost:8000/api/session/', {
    credentials: 'include',
  })
  if (!response.ok) throw new Error('Unable to connect to the backend.')
  return response.json()
}

export async function apiPost(path, body) {
  await ensureSession()
  const response = await fetch(`http://localhost:8000${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(body),
  })

  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    const detail = data?.detail
      || data?.error
      || (data && Object.values(data).flat()[0])
      || 'The request could not be completed.'
    throw new Error(detail)
  }
  return data
}
