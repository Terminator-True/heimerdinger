import { describe, it, expect } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { SettingsProvider } from './SettingsProvider'

// Contract test: any view's 401 dispatches this event and the shell must
// open the settings dialog exactly once — no loop, no close-spam.
describe('unauthorized-event contract', () => {
  it('opens the SettingsDialog once when heimerdinger:unauthorized is dispatched', () => {
    render(
      <SettingsProvider>
        <div>shell content</div>
      </SettingsProvider>,
    )

    act(() => {
      window.dispatchEvent(new CustomEvent('heimerdinger:unauthorized'))
    })

    const dialogs = screen.getAllByRole('dialog', { name: 'Configuración' })
    expect(dialogs).toHaveLength(1)
    // Re-dispatching while open must not stack a second dialog.
    act(() => {
      window.dispatchEvent(new CustomEvent('heimerdinger:unauthorized'))
    })
    expect(screen.getAllByRole('dialog', { name: 'Configuración' })).toHaveLength(1)
    expect(screen.getByText('shell content')).toBeTruthy()
  })
})
