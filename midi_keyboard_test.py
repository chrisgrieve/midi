import mido

# List available MIDI ports
print("Available MIDI input ports:")
for port in mido.get_input_names():
    print(port)

print("\nAvailable MIDI output ports:")
for port in mido.get_output_names():
    print(port)
