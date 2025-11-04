from sys import maxsize
from collections import defaultdict
from datetime import datetime

from plex.connection import PlexConnection
from plex.music import PlexMusic
from utils.weighted_picker import WeightedPicker


class PlexPlaylistBuilder():
	def __init__(self, username=None, password=None, resource=None, server_url=None, token=None):
		plex_library = PlexConnection(
			username=username, password=password, resource=resource, server_url=server_url, token=token,
		).music_library
		self.music_library = PlexMusic(plex_library)

		# Private properties
		self._popular_tracks = self._recent_tracks = self._spice_tracks = None
		self._play_count_min = self._play_count_max = None
		self._last_played_min = self._last_played_max = None
		self._artist_play_count_min = self._artist_play_count_max = None
		self._album_play_count_min = self._album_play_count_max = None
		self._genre_play_count_min = self._genre_play_count_max = None
		self._genre_play_counts = self._genre_song_counts = None

	def build_playlist(self, playlist_title=None, track_count=50):
		print('Building track groupings...')
		
		# Validate track lists before creating pickers
		popular_tracks = self.popular_tracks
		recent_tracks = self.recent_tracks
		spice_tracks = self.spice_tracks
		
		if not popular_tracks:
			raise ValueError("Popular tracks list is empty. No tracks available with play counts.")
		if not recent_tracks:
			raise ValueError("Recent tracks list is empty. No recently played tracks found.")
		if not spice_tracks:
			raise ValueError("Spice tracks list is empty. No tracks available for random selection.")
		
		playlist_songs = set()
		popular_picker = WeightedPicker(popular_tracks)
		recent_picker = WeightedPicker(recent_tracks)
		spice_picker = WeightedPicker(spice_tracks)
		playlist_slots = [
			popular_picker, recent_picker, popular_picker,
			spice_picker, popular_picker, recent_picker
		]
		print('Building track groupings... DONE.')
		print('Generating playlist...')
		while len(playlist_songs) < track_count:
			for slot_picker in playlist_slots:
				next_track = slot_picker.next()['track']
				playlist_songs.add(next_track)
				if len(playlist_songs) >= track_count:
					break
		playlist_songs = list(playlist_songs)
		print('Generating playlist... DONE')

		print(f'Updating playlist {playlist_title}... ')
		self.music_library.replace_playlist_tracks(playlist_title, playlist_songs)
		print(f'Updating playlist {playlist_title}... DONE')
		

	# Properties

	@property
	def popular_tracks(self):
		if self._popular_tracks is None:
			self._popular_tracks = self._generate_popular_tracks()
		return self._popular_tracks

	@property
	def recent_tracks(self):
		if self._recent_tracks is None:
			self._recent_tracks = self._generate_recently_played_tracks()
		return self._recent_tracks

	@property
	def spice_tracks(self):
		if self._spice_tracks is None:
			self._spice_tracks = self._generate_spice_tracks()
		return self._spice_tracks

	@property
	def play_count_min(self):
		if self._play_count_min is None:
			results = self.music_library.library_search('viewCount:asc', 'track', 1)
			if results and len(results) > 0:
				self._play_count_min = results[0].viewCount or 0
			else:
				self._play_count_min = 0
		return self._play_count_min

	@property
	def play_count_max(self):
		if self._play_count_max is None:
			results = self.music_library.top_played_tracks(limit=1)
			if results and len(results) > 0:
				self._play_count_max = results[0].viewCount or 0
			else:
				self._play_count_max = 0
		return self._play_count_max

	@property
	def last_played_min(self):
		if self._last_played_min is None:
			self._build_mix_max_values()
		return self._last_played_min

	@property
	def last_played_max(self):
		if self._last_played_max is None:
			results = self.music_library.recently_played_tracks(limit=1)
			if results and len(results) > 0 and results[0].lastViewedAt:
				self._last_played_max = results[0].lastViewedAt
			else:
				self._last_played_max = datetime.utcnow()
		return self._last_played_max

	@property
	def artist_play_count_min(self):
		if self._artist_play_count_min is None:
			results = self.music_library.library_search('viewCount:asc', 'artist', 1)
			if results and len(results) > 0:
				self._artist_play_count_min = results[0].viewCount or 0
			else:
				self._artist_play_count_min = 0
		return self._artist_play_count_min

	@property
	def artist_play_count_max(self):
		if self._artist_play_count_max is None:
			results = self.music_library.library_search('viewCount:desc', 'artist', 1)
			if results and len(results) > 0:
				self._artist_play_count_max = results[0].viewCount or 0
			else:
				self._artist_play_count_max = 0
		return self._artist_play_count_max

	@property
	def album_play_count_min(self):
		if self._album_play_count_min is None:
			results = self.music_library.library_search('viewCount:asc', 'album', 1)
			if results and len(results) > 0:
				self._album_play_count_min = results[0].viewCount or 0
			else:
				self._album_play_count_min = 0
		return self._album_play_count_min

	@property
	def album_play_count_max(self):
		if self._album_play_count_max is None:
			results = self.music_library.library_search('viewCount:desc', 'album', 1)
			if results and len(results) > 0:
				self._album_play_count_max = results[0].viewCount or 0
			else:
				self._album_play_count_max = 0
		return self._album_play_count_max

	@property
	def genre_play_count_min(self):
		if self._genre_play_count_min is None:
			self._build_mix_max_values()
		if self._genre_play_count_min is None:
			self._genre_play_count_min = 0
		return self._genre_play_count_min

	@property
	def genre_play_count_max(self):
		if self._genre_play_count_max is None:
			self._build_mix_max_values()
		return self._genre_play_count_max

	@property
	def genre_play_counts(self):
		if self._genre_play_counts is None:
			self._build_mix_max_values()
		return self._genre_play_counts

	@property
	def genre_song_counts(self):
		if self._genre_song_counts is None:
			self._build_mix_max_values()
		return self._genre_song_counts


	# Private methods

	def _build_mix_max_values(self):
		# Convert calculateMaxMinValues
		print('Building min/max music library values...')
		min_played_at = datetime.utcnow()
		genre_play_counts = defaultdict(int)
		genre_song_counts = defaultdict(int)
		progress_set = set()
		for artist_count, artist in enumerate(self.music_library.all_artists()):
			progress = round((artist_count / self.music_library.total_artist_count) * 100)
			if progress % 5 == 0 and progress not in progress_set:
				progress_set.add(progress)
				print(f'Building min/max music library values... {progress}%')

			artist_play_count = artist.viewCount
			artist_last_played = artist.lastViewedAt
			artist_track_count = len(artist.tracks())
			if artist_last_played and artist_last_played < min_played_at:
				min_played_at = artist_last_played
			for genre in artist.styles:
				genre_id = genre.id
				genre_play_counts[genre_id] += artist_play_count
				genre_song_counts[genre_id] += artist_track_count

		min_genre_plays = maxsize
		max_genre_plays = 0
		for genre in genre_play_counts:
			play_count = genre_play_counts[genre]
			max_genre_plays = max(play_count, max_genre_plays)
			min_genre_plays = min(play_count, min_genre_plays)

		# Handle case where no genres have play counts
		if min_genre_plays == maxsize:
			min_genre_plays = 0

		self._genre_play_counts = genre_play_counts
		self._genre_song_counts = genre_song_counts
		self._genre_play_count_min = min_genre_plays
		self._genre_play_count_max = max_genre_plays
		self._last_played_min = min_played_at
		print('Building min/max music library values... DONE')

	def _get_track_rating_normalized(self, plex_track_rating):
		rating_normalized_to_apply = 0
		if plex_track_rating:
			rating_normalized = self._normalize(
				plex_track_rating, max_value=10, min_value=1
			)
			if rating_normalized > 0:
				rating_normalized_to_apply = rating_normalized / 2
		return rating_normalized_to_apply

	def _get_track_last_played_normalized(self, plex_track_last_played):
		last_played_adjusted = 0
		if plex_track_last_played:
			last_played_normalized = self._normalize(
				plex_track_last_played.timestamp(),
				max_value=self.last_played_max.timestamp(),
				min_value=self.last_played_min.timestamp()
			)
			last_played_adjusted = (1 - last_played_normalized)
			if last_played_adjusted > 0.5:
				last_played_adjusted = last_played_adjusted * 2
			elif last_played_adjusted < 0:
				last_played_adjusted = 0
		return last_played_adjusted

	def _get_artist_playcount_normalized(self, plex_track_artist):
		return self._normalize(
			plex_track_artist.viewCount,
			max_value=self.artist_play_count_max, min_value=self.artist_play_count_min
		)

	def _get_genre_playcount_normalized(self, plex_track_artist):
		genre_play_count_normalized = 0
		genre_play_count_sum = 0
		genre_play_count_total = 0
		for track_genre in plex_track_artist.styles:
			genre_play_count_total += 1
			genre_play_count = self.genre_play_counts.get(track_genre.id, 0)
			genre_norm = self._normalize(
				genre_play_count, max_value=self.genre_play_count_max, min_value=self.genre_play_count_min
			)
			genre_play_count_sum += genre_norm
		if genre_play_count_sum > 0 and genre_play_count_total > 0:
			genre_play_count_normalized = genre_play_count_sum / genre_play_count_total
		return genre_play_count_normalized


	def _build_track_dict(self, plex_track, category):
		# Convert generateSongDict

		play_count_normalized = self._normalize(
			plex_track.viewCount, max_value=self.play_count_max, min_value=self.play_count_min
		)

		track_artist = plex_track.artist()
		rating_normalized_to_apply = self._get_track_rating_normalized(plex_track.userRating)
		last_played_adjusted = self._get_track_last_played_normalized(plex_track.lastViewedAt)
		artist_play_count_normalized = self._get_artist_playcount_normalized(track_artist)
		genre_play_count_normalized = self._get_genre_playcount_normalized(track_artist)

		weight = (play_count_normalized + rating_normalized_to_apply + last_played_adjusted +
				 artist_play_count_normalized + (genre_play_count_normalized / 2))
		weight = (1 + weight) * 1000

		return {
			'track': plex_track,
			'weight': round(weight),
			'category': category
		}

	def _normalize(self, input_value, min_value=0, max_value=1):
		if input_value is None or min_value is None or max_value is None:
			return 0
		if max_value == min_value:
			return 0
		return (input_value - min_value) / (max_value - min_value)

	def _generate_recently_played_tracks(self):
		print('Generating recently played tracks...')
		recent_tracks = []
		play_count = self.music_library.total_track_count * 0.15
		if play_count > 500:
			play_count = 500
		if play_count < 1:
			play_count = 1

		tracks_processed = 0
		tracks_errored = 0
		
		for track in self.music_library.recently_played_tracks(limit=play_count):
			tracks_processed += 1
			# Include tracks even if lastViewedAt is None - they'll still be weighted appropriately
			try:
				track_data = self._build_track_dict(track, 'recent')
				recent_tracks.append(track_data)
			except Exception as e:
				# Skip tracks that cause errors during processing
				tracks_errored += 1
				print(f'Warning: Skipping track due to error: {e}')
				continue

		print(f'Generating recently played tracks... DONE. (Processed: {tracks_processed}, Added: {len(recent_tracks)}, Errors: {tracks_errored})')
		return recent_tracks

	def _generate_popular_tracks(self):
		print('Generating popular tracks...')
		popular_tracks = []
		play_count = self.music_library.total_track_count * 0.15
		if play_count > 500:
			play_count = 500
		if play_count < 1:
			play_count = 1

		tracks_processed = 0
		tracks_errored = 0
		
		# Try to get top played tracks first
		tracks = list(self.music_library.top_played_tracks(limit=play_count))
		
		# If no tracks from top_played_tracks, fallback to library search sorted by viewCount
		if not tracks:
			print('No tracks from top_played_tracks, using library search fallback...')
			tracks = list(self.music_library.library_search('viewCount:desc', 'track', limit=play_count))
		
		for track in tracks:
			tracks_processed += 1
			# Include tracks even if viewCount is 0 or None - they'll still be weighted appropriately
			try:
				track_data = self._build_track_dict(track, 'popular')
				popular_tracks.append(track_data)
			except Exception as e:
				# Skip tracks that cause errors during processing
				tracks_errored += 1
				print(f'Warning: Skipping track due to error: {e}')
				continue

		print(f'Generating popular tracks... DONE. (Processed: {tracks_processed}, Added: {len(popular_tracks)}, Errors: {tracks_errored})')
		return popular_tracks

	def _generate_spice_tracks(self):
		print('Generating spice tracks...')
		spice_tracks = []
		for track in self.music_library.library_search('random', 'track', 300):
			try:
				track_data = self._build_track_dict(track, 'spice')
				spice_tracks.append(track_data)
			except Exception as e:
				# Skip tracks that cause errors during processing
				print(f'Warning: Skipping track due to error: {e}')
				continue

		print('Generating spice tracks... DONE.')
		return spice_tracks

