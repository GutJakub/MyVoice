import unittest
from unittest.mock import Mock, call, patch

from spotipy import SpotifyException

from myvoice.integrations.spotify import SpotifyClient


def device(name='LENOVOJAKUB', active=False, restricted=False, device_id='lenovo'):
    return {'name': name, 'id': device_id, 'is_active': active, 'is_restricted': restricted}


class SpotifyPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.spotify = SpotifyClient.__new__(SpotifyClient)
        self.spotify.client = Mock()
        self.spotify.find_best_playlist = Mock(return_value=(
            {'name': 'Jazz', 'uri': 'spotify:playlist:jazz'}, 'token_match', 100))
        self.spotify.client.devices.return_value = {'devices': [device()]}
        self.sleep = patch('myvoice.integrations.spotify.time.sleep').start()
        self.addCleanup(patch.stopall)

    def test_inactive_preferred_device_transfers_before_explicit_playback_and_shuffle(self):
        self.spotify.client.devices.return_value = {'devices': [
            device('Phone', True, device_id='phone'), device()]}
        result = self.spotify.play_playlist('Jazz', shuffle=True)
        self.assertIn('Playing playlist Jazz', result)
        self.assertEqual(self.spotify.client.mock_calls, [
            call.devices(),
            call.transfer_playback(device_id='lenovo', force_play=False),
            call.start_playback(device_id='lenovo', context_uri='spotify:playlist:jazz'),
            call.shuffle(True, device_id='lenovo'),
        ])
        self.sleep.assert_not_called()

    def test_active_device_needs_no_transfer(self):
        self.spotify.client.devices.return_value = {'devices': [device(active=True)]}
        self.spotify.play_playlist('Jazz')
        self.spotify.client.transfer_playback.assert_not_called()
        self.spotify.client.shuffle.assert_called_once_with(False, device_id='lenovo')

    def test_restricted_preferred_device_is_ignored_and_active_fallback_wins(self):
        self.spotify.client.devices.return_value = {'devices': [
            device(restricted=True), device('Other', device_id='other'),
            device('Phone', active=True, device_id='phone')]}
        self.spotify.play_playlist('Jazz')
        self.spotify.client.start_playback.assert_called_once_with(
            device_id='phone', context_uri='spotify:playlist:jazz')
        self.spotify.client.transfer_playback.assert_not_called()

    def test_unusable_or_absent_devices_return_message(self):
        for devices in ([], [device(restricted=True)], [device(device_id=None)]):
            with self.subTest(devices=devices):
                self.spotify.client.devices.return_value = {'devices': devices}
                self.assertIn('No usable Spotify device', self.spotify.play_playlist('Jazz'))
        self.spotify.client.start_playback.assert_not_called()
        self.spotify.client.transfer_playback.assert_not_called()

    def test_not_ready_playback_retries_then_succeeds(self):
        self.spotify.client.start_playback.side_effect = [
            SpotifyException(404, -1, 'Player command'),
            SpotifyException(404, -1, 'Player command'), None]
        self.assertIn('Playing playlist Jazz', self.spotify.play_playlist('Jazz'))
        self.assertEqual(self.sleep.call_args_list, [call(0.25), call(0.5)])
        self.assertEqual(self.spotify.client.start_playback.call_args_list, [
            call(device_id='lenovo', context_uri='spotify:playlist:jazz')] * 3)
        self.spotify.client.transfer_playback.assert_called_once()

    def test_exhausted_retries_return_failure_without_shuffle(self):
        self.spotify.client.start_playback.side_effect = SpotifyException(404, -1, 'Player command')
        result = self.spotify.play_playlist('Jazz')
        self.assertIn('Could not start Spotify playback on LENOVOJAKUB', result)
        self.assertEqual(self.spotify.client.start_playback.call_count, 3)
        self.spotify.client.shuffle.assert_not_called()

    def test_non_readiness_errors_are_not_retried(self):
        self.spotify.client.start_playback.side_effect = SpotifyException(403, -1, 'Forbidden')
        self.assertIn('HTTP 403', self.spotify.play_playlist('Jazz'))
        self.spotify.client.start_playback.assert_called_once()
        self.sleep.assert_not_called()

    def test_transfer_failure_does_not_start_or_shuffle(self):
        self.spotify.client.transfer_playback.side_effect = SpotifyException(403, -1, 'Forbidden')
        self.assertIn('Could not start Spotify playback', self.spotify.play_playlist('Jazz'))
        self.spotify.client.start_playback.assert_not_called()
        self.spotify.client.shuffle.assert_not_called()

    def test_shuffle_failure_does_not_claim_playback_failed(self):
        self.spotify.client.shuffle.side_effect = SpotifyException(403, -1, 'Forbidden')
        result = self.spotify.play_playlist('Jazz')
        self.assertIn('Playing playlist Jazz', result)
        self.assertIn('could not set shuffle', result)

    def test_low_confidence_match_does_not_touch_devices(self):
        self.spotify.find_best_playlist.return_value = (None, 'none', 0)
        self.assertIn('Could not confidently find playlist', self.spotify.play_playlist('unknown'))
        self.spotify.client.devices.assert_not_called()


if __name__ == '__main__':
    unittest.main()
