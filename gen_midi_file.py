from midiutil import MIDIFile
from mingus.core import chords

chord_progression = ["Cmaj7", "Cmaj7", "Fmaj7", "Gdom7"]

NOTES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
OCTAVES = list(range(11))
NOTES_IN_OCTAVE = len(NOTES)

errors = {
    'notes': 'Bad input, please refer this spec-\n'
}


def swap_accidentals(note):
    if note == 'Db':
        return 'C#'
    if note == 'D#':
        return 'Eb'
    if note == 'E#':
        return 'F'
    if note == 'Gb':
        return 'F#'
    if note == 'G#':
        return 'Ab'
    if note == 'A#':
        return 'Bb'
    if note == 'B#':
        return 'C'

    return note


def note_to_number(note: str, octave: int) -> int:
    print(f"note: {note}")
    note = swap_accidentals(note)
    print(f"note: {note}")
    assert note in NOTES, errors['notes']
    assert octave in OCTAVES, errors['notes']

    note = NOTES.index(note)
    note += (NOTES_IN_OCTAVE * octave)

    assert 0 <= note <= 127, errors['notes']

    return note
  
def main():

  arpegio_notes = []
  base_notes = []
  my_chords = []
  for chord in chord_progression:
    notes = chords.from_shorthand(chord)
    print(f"chord: {chord} notes: {notes}")
    arpegio_notes.extend(notes)
    my_chords.append(notes)
  print(f"arpegio_notes: {arpegio_notes}")

  arpegio_codes = []
  bass_codes = []
  chord_codes = []
  
  for note in arpegio_notes:
    OCTAVE = 4
    print(f"note: {note}")
    if note in NOTES:
      arpegio_codes.append(note_to_number(note, OCTAVE))
      bass_codes.append(note_to_number(note, OCTAVE-1))
    
 
  for chord in my_chords:
    codes = []
    for note in chord:
      codes.append(note_to_number(note, OCTAVE))
      chord_codes.append(codes)
    

    
  
  

  print(f"arpegio_notes: {arpegio_notes}")
  track = 0
  channel = 0
  time = 0  # In beats
  duration = 1  # In beats
  tempo = 120  # In BPM
  volume = 100  # 0-127, as per the MIDI standard

  MyMIDI = MIDIFile(1)  # One track, defaults to format 1 (tempo track is created
  # automatically)
  MyMIDI.addTempo(track, time, tempo)

  for i, chord in enumerate(chord_codes):
    print(f"{i} {chord}")
    for j, code in enumerate(chord):
      print(f"{j} {code}")
      MyMIDI.addNote(track, channel, code, (time + i)//4, duration, volume)
    #MyMIDI.addNote(track, channel, pitch, time + i, duration, volume)

      #MyMIDI.addNote(track, channel+1, bass_codes[i],(time + i)//4, duration, volume)

  with open("pure-edm-fire-arpeggio.mid", "wb") as output_file:
    MyMIDI.writeFile(output_file)
    
  
if __name__=="__main__":
  main()