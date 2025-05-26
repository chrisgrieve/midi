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

    def clear(self):
        self.notes.clear()

    def add_notes(self, new_notes):
        self.notes.extend(new_notes)

    def append(self, note):
        self.notes.append(note)

    def sort(self, key):
        self.notes.sort(key=key)

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

def record_midi(is_playing, song, input_port=None):
    """Continuously records notes and adds them to the sequence."""
    logging.info("record_midi...")
    active_notes = {}

    with mido.open_input(input_port) as inport:
        while is_playing():
            for msg in inport.iter_pending():
                if not (active_notes or song.get_playing_phrase()):
                    set_seq_start_time()

                msg.time = get_seq_elapsed_time()
                if msg.type == 'note_on':
                    active_notes[msg.note] = Note(msg)
                elif msg.type == 'note_off' and msg.note in active_notes:
                    note = active_notes.pop(msg.note)
                    note.set_note_off(msg)
                    song.get_playing_phrase().append(note)
                    n_second_print(f"\nRECORD MENU - Added note: {note} press q to quit recording...", 1)
                    song.get_playing_phrase().sort(key=lambda x: x.start_time)
            if keyboard.is_pressed('q'):
                logging.info("Stopped adding notes.")
                for note in song.get_playing_phrase():
                    logging.debug(note)
                return

def play_midi_smarter(is_playing, song, output_port=None):
    """Plays recorded notes, handling overlapping notes more efficiently."""
    logging.info("play_midi_smarter...")
    with mido.open_output(output_port) as outport:
        events = []
        tempo_change = False
        update_event_queue(events, song)
        recorded_notes_size = len(song.get_playing_phrase())

        while is_playing():
            if(recorded_notes_size != len(song.get_playing_phrase())):
                update_event_queue(events, song.get_playing_phrase())
                recorded_notes_size = len(song.get_playing_phrase())

            if tempo_change:
                events = []
                update_event_queue(events, song.get_playing_phrase())
                tempo_change = False

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

                if keyboard.is_pressed('+' ):
                    if not tempo_change:
                        n_second_print("increasing tempo...", 1)
                        song.set_playing_phrase(change_tempo(song.get_playing_phrase(), 0.9))
                        tempo_change = True
                    break

                if keyboard.is_pressed('-'):
                    if not tempo_change:
                        n_second_print("decreasing tempo...", 1)
                        song.set_playing_phrase(change_tempo(song.get_playing_phrase(), 1.1))
                        tempo_change = True
                    break


def change_tempo(song, multiplier):
    result = Phrase()
    for note in song.get_playing_phrase():
        note.start_time = note.start_time * multiplier
        note.end_time = note.end_time * multiplier
        result.notes.append(note)
    return result


def update_event_queue(events, song):
    logging.debug(f"song: {song}")
    logging.debug(f"song.get_playing_phrase(): {song.get_playing_phrase()}")
    for note in song.get_playing_phrase().notes:
        # Push note on and off events to the priority queue
        heapq.heappush(events, (note.start_time, note.note_on_msg, 'on'))
        heapq.heappush(events, (note.end_time, note.note_off_msg, 'off'))


def start_overdub_loop(song, input_port=None, output_port=None):
    """Starts looping playback and allows overdubbing."""
    logging.info("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playback_thread = threading.Thread(target=play_midi_smarter, args=(is_playing, song, output_port))
    playback_thread.start()

    logging.info("dropping in to start_loop...")

    # Allow real-time recording while playing
    record_midi(is_playing, song, input_port)

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def start_play_loop(song, input_port=None, output_port=None):
    """Starts looping playback and allows overdubbing."""
    logging.info("start_loop...")
    playing = [True]  # Mutable object to control playback state

    def is_playing():
        return playing[0]

    def stop_playing():
        playing[0] = False

    # Start playback in a separate thread
    playback_thread = threading.Thread(target=play_midi_smarter, args=(is_playing, song, output_port))
    playback_thread.start()

    logging.info("dropping in to start_loop...")

    while is_playing():
        n_second_print(f"\nPLAY MENU: press q to quit playing...", 5)

        if keyboard.is_pressed('q'):
            logging.info("Stop playing notes.")
            break

    stop_playing()
    playback_thread.join()  # Wait for playback to finish

def main():
    song = Song(10)
    input_port = find_input_port()
    output_port = find_output_port()

    while True:
        n_second_print("\nMAIN MENU: Press 'r' to record, 'p' to just play, 'o' to play & overdub, 's' to save, 'l' to load, 'x' to exit.", 5)

        if keyboard.is_pressed('r'):
            song.get_playing_phrase().clear()  # Clear previous recordings
            set_seq_start_time()
            record_midi(lambda: True, song.get_playing_phrase(), input_port)

        if keyboard.is_pressed('o'):
            start_overdub_loop(song, input_port, output_port)

        if keyboard.is_pressed('p'):
            start_play_loop(song, input_port, output_port)

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
