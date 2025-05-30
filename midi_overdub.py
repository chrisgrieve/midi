import mido
import time
import keyboard  # To detect laptop key presses
import threading  # To allow concurrent playback and recording
import logging
from threading import Event
import heapq
from collections import defaultdict


# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

start_time = 0.00
event = Event()

def n_second_print(output_string, t=1):
    if (int(time.time()) * 10) % (10 * t) == 0:
        print(f"{output_string}")

def find_input_port():
    result = None
    # List available MIDI ports
    logging.info("Available MIDI input ports:")
    for port in mido.get_input_names():
        if "CASIO" in port:
            result = port

    logging.info(f"found input port: {result}")
    return result

def find_output_port():
    result = None
    logging.info("Available MIDI output ports:")
    for port in mido.get_output_names():
        if "CASIO" in port:
            result = port

    logging.info(f"found output port: {result}")
    return result

def set_seq_start_time():
    global start_time
    start_time = time.time()
    logging.debug(f"start_time: {start_time}")

def get_seq_elapsed_time():
    logging.debug(f"start_time: {start_time}")
    logging.debug(f"get_seq_elapsed_time: {time.time() - start_time}")
    return time.time() - start_time

class Note:
    def __init__(self, note_on_msg, note_off_msg=None):
        self.end_time = None
        self.note_off_msg = None
        self.note_on_msg = note_on_msg
        self.start_time = note_on_msg.time
        if note_off_msg:
            self.set_note_off(note_off_msg)

    def set_note_off(self, note_off_msg):
        self.note_off_msg = note_off_msg
        self.end_time = note_off_msg.time

    def __repr__(self):
        return f'Note (ON: {self.note_on_msg}, OFF: {self.note_off_msg})'


class Phrase:
    def __init__(self):
        self.notes = []
        self.updated = False

    def clear(self):
        self.notes.clear()
        self.updated = True

    def add_notes(self, new_notes):
        self.notes.extend(new_notes)
        self.updated = True

    def append(self, note):
        self.notes.append(note)
        self.updated = True

    def sort(self, key):
        self.notes.sort(key=key)

    def change_tempo(self, multiplier):
        for note in self.notes:
            note.start_time = note.start_time * multiplier
            note.end_time = note.end_time * multiplier
            self.updated = True

    def import_midi(self, filename):
        self.clear()
        mid = mido.MidiFile(filename)
        ticks_per_beat = mid.ticks_per_beat
        tempo = 500000
        note_starts = defaultdict(list)
        result = Phrase()

        abs_ticks = 0
        current_time = 0

        for msg in mid.tracks[0]:
            abs_ticks += msg.time
            current_time = mido.tick2second(abs_ticks, ticks_per_beat, tempo)

            if msg.type == 'set_tempo':
                tempo = msg.tempo
            elif msg.type == 'note_on':
                note_on_msg = msg.copy(time=current_time)
                note_starts[msg.note].append(note_on_msg)
            elif msg.type == 'note_off' and note_starts[msg.note]:
                note_on_msg = note_starts[msg.note].pop(0)
                note_off_msg = msg.copy(time=current_time)
                note = Note(note_on_msg, note_off_msg)
                self.append(note)

    def export_to_midi(self, filename='output.mid', bpm=120):
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        tempo = mido.bpm2tempo(bpm)
        track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))

        events = []
        for note in self.notes:
            events.append({'time': note.start_time, 'msg': mido.Message('note_on', note=note.note_on_msg.note,
                                                                        velocity=note.note_on_msg.velocity)})
            events.append({'time': note.end_time, 'msg': mido.Message('note_off', note=note.note_off_msg.note,
                                                                      velocity=note.note_off_msg.velocity)})

        events.sort(key=lambda e: e['time'])
        last_time = 0
        for event in events:
            delta_ticks = int(mido.second2tick(event['time'] - last_time, mid.ticks_per_beat, tempo))
            event['msg'].time = delta_ticks
            track.append(event['msg'])
            last_time = event['time']

        mid.save(filename)

    def __iter__(self):
        return iter(self.notes)

    def __len__(self):
        return len(self.notes)



class Song:
    def __init__(self, num_phrases=9):
        self.phrases = [Phrase() for i in range(num_phrases)]
        self.playing_phrase_index = 0

    def get_playing_phrase(self):
        logging.debug(f"self.phrases: {self.phrases}")
        return self.phrases[self.playing_phrase_index]

    def set_playing_phrase(self, phrase):
        self.phrases[self.playing_phrase_index] = phrase
class Recorder:
    def __init__(self, input_port):
        self.input_port = input_port

    def record_phrase(self, phrase, is_playing):
        logging.info("Recorder: recording started...")
        active_notes = {}

        with mido.open_input(self.input_port) as inport:
            while is_playing():
                for msg in inport.iter_pending():
                    if not (active_notes or phrase):
                        set_seq_start_time()

                    msg.time = get_seq_elapsed_time()
                    if msg.type == 'note_on':
                        active_notes[msg.note] = Note(msg)
                    elif msg.type == 'note_off' and msg.note in active_notes:
                        note = active_notes.pop(msg.note)
                        note.set_note_off(msg)
                        phrase.append(note)
                        n_second_print(f"\nRECORD MENU - Added note: {note} press q to quit recording...", 1)
                        phrase.sort(key=lambda x: x.start_time)

                if keyboard.is_pressed('q'):
                    logging.info("Recorder: recording stopped.")
                    for note in phrase:
                        logging.debug(note)
                    return

class Player:
    def __init__(self, output_port):
        self.output_port = output_port
        self.tempo_multiplier = 1.0

    def update_event_queue(self, events, phrase):
        events.clear()
        for note in phrase.notes:
            # Push note on and off events to the priority queue
            note.start_time = note.start_time * self.tempo_multiplier
            note.end_time = note.end_time * self.tempo_multiplier
            heapq.heappush(events, (note.start_time, note.note_on_msg, 'on'))
            heapq.heappush(events, (note.end_time, note.note_off_msg, 'off'))

    def play(self, phrase: Phrase, is_playing):
        logging.info("playing...")
        with mido.open_output(self.output_port) as outport:
            events = []
            tempo_change = False
            self.update_event_queue(events, phrase)
            recorded_notes_size = len(phrase)

            while is_playing():
                # if (recorded_notes_size != len(phrase)):
                if phrase.updated:
                    self.update_event_queue(events, phrase)
                    phrase.updated = False

                set_seq_start_time()
                loop_events = list(events)  # Create a copy of the events heap
                heapq.heapify(loop_events)  # Ensure it's a valid heap
                while loop_events:
                    event_time, msg, event_type = heapq.heappop(loop_events)
                    logging.debug(f"event_time: {event_time})")
                    sleep_time = event_time - get_seq_elapsed_time()
                    logging.debug(f"sleep_time: {sleep_time})")
                    event.wait(max(0, sleep_time))
                    outport.send(msg)
                    logging.debug(f"Played: {msg} ({event_type})")


def update_event_queue(events, song):
    logging.debug(f"song: {song}")
    logging.debug(f"song.get_playing_phrase(): {song.get_playing_phrase()}")
    for note in song.get_playing_phrase().notes:
        # Push note on and off events to the priority queue
        heapq.heappush(events, (note.start_time, note.note_on_msg, 'on'))
        heapq.heappush(events, (note.end_time, note.note_off_msg, 'off'))


def start_overdub_loop(song, player, recorder):
    """Starts looping playback and allows overdubbing.
    :param recorder:
    """
    logging.info("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    phrase = song.get_playing_phrase()
    playback_thread = threading.Thread(target=player.play, args=(phrase, is_playing))
    playback_thread.start()

    logging.info("dropping in to start_loop...")

    # Allow real-time recording while playing
    recorder.record_phrase(phrase, is_playing)

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def start_play_loop(song, player):
    """Starts looping playback and allows overdubbing."""
    logging.info("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playing_phrase = song.get_playing_phrase()
    playback_thread = threading.Thread(target=player.play, args=(playing_phrase, is_playing))
    playback_thread.start()

    logging.info("dropping in to start_loop...")

    while is_playing():
        n_second_print(f"\nPLAY MENU: press q to quit playing, +/- to increase/decrease tempo...", 5)

        event = keyboard.read_event(suppress=False)

        if event.event_type == 'down':  # Only respond on key press, not release
            if event.name == '+':
                player.tempo_multiplier = max(0.1, player.tempo_multiplier * 0.9)
                print(f"Tempo: {player.tempo_multiplier:.2f}x")

            elif event.name == '-':
                player.tempo_multiplier = min(5.0, player.tempo_multiplier * 1.1)
                print(f"Tempo: {player.tempo_multiplier:.2f}x")

            elif event.name == '0':
                player.tempo_multiplier = 1.0
                print("Tempo reset to 1.0x")

            elif event.name == 'q':
                print("Exiting play loop.")
                stop_playing()

        time.sleep(0.01)  # Tiny sleep to avoid high CPU usage



    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def main():
    song = Song(10)
    input_port = find_input_port()
    output_port = find_output_port()
    player = Player(output_port)
    recorder = Recorder(input_port)

    while True:
        n_second_print("\nMAIN MENU: Press 'r' to record, 'p' to just play, 'o' to play & overdub, 's' to save, 'l' to load, 'x' to exit.", 5)

        if keyboard.is_pressed('r'):
            song.get_playing_phrase().clear()  # Clear previous recordings
            set_seq_start_time()
            recorder.record_phrase(song.get_playing_phrase(), lambda: True)

        if keyboard.is_pressed('o'):
            start_overdub_loop(song, player, recorder)

        if keyboard.is_pressed('p'):
            start_play_loop(song, player)

        if keyboard.is_pressed('s'):
            # Save the recorded notes as a timestamped MIDI file
            filename = input("Enter the filename of the MIDI file to save as: ").strip()
            if not filename:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"recording_{timestamp}.mid"
            filename = filename + ".mid" if not filename.endswith(".mid") else filename
            song.get_playing_phrase().export_to_midi(filename=filename)
            logging.info(f"Saved recording as {filename}")

        if keyboard.is_pressed('l'):
            # Load MIDI file into song.get_playing_phrase()
            filename = input("Enter the filename of the MIDI file to load: ").strip()
            filename = filename + ".mid" if not filename.endswith(".mid") else filename
            try:
                phrase = Phrase()
                phrase.import_midi(filename)
                song.set_playing_phrase(phrase)
                logging.info(f"Successfully loaded MIDI file: {filename}")
            except FileNotFoundError:
                logging.error(f"File not found: {filename}")
            except Exception as e:
                logging.error(f"Failed to load MIDI file: {e}")

        if keyboard.is_pressed('x'):
            logging.info("Exiting program.")
            break

        time.sleep(0.1)  # Small delay to prevent high CPU usage

if __name__ == "__main__":
    main()
