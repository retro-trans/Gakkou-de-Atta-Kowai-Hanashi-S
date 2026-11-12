# Building in-game debug tools for another game — guide for agents

How to build a debug kit for a translation project on any platform and any emulator.
With it you can see any translated text in the real game within seconds, instead of
playing to it with screenshots and key presses. This project's implementation and its
addresses are in `docs/debug_tools.md`; this guide holds only the general method.

Build the tools in this order. Each step is useful by itself, and the later steps reuse
the earlier ones.

| Step | Tool | Gives you | Needs from the game |
| --- | --- | --- | --- |
| 1 | emulator control + debugger link | start/stop the project emulator, read/write memory | nothing |
| 2 | input + screenshots | virtual buttons and framebuffer captures that need no window focus | the input-read routine |
| 3 | savestate reader | memory and video memory out of savestates, offline | the savestate format |
| 4 | function tracer | which routines run when you press a button | candidate addresses |
| 5 | safe halt + state helpers | a moment when code can be rewritten; the script interpreter's state | thread state, interpreter struct |
| 6 | hot reload | a new build inside an old savestate | what the build adds and where |
| 7 | scene preview | any script text on screen at once | the interpreter's start / run routines |

## 0. Ground rules

- **Use a portable emulator inside the project** (`work/emulator/<name>/`) with its own
  settings. The tools must find and stop only that process, matched by its full path,
  never an emulator the user runs themself.
- **Choose an emulator with a remote debugger** (a GDB stub or a scripting / debug API)
  that offers memory read/write, registers, breakpoints and continue. Without one,
  only the screenshot-and-keys way is left.
- **Configure the debugger port and keep it in an environment variable.** The default
  port is often taken by another emulator.
- **Run one instance at a time.** A loop that restarts the emulator must wait for the
  old process to exit; otherwise duplicate instances fight over the port.
- **Name and list savestates.** Keep them in `work/emulator/states/` with the build and
  the place in the name (`v026_ep1_battle_start`), and list them in the game's
  `docs/debug_tools.md`.
- **Never delete old screenshots or runs.** Write to a new folder.
- **Keep non-ASCII text off the console.** It may come out garbled; set UTF-8 output and
  write such text to files.

## 1. Debugger link

A small client for the emulator's debug protocol is enough. It needs:
- memory read and write, in chunks the stub accepts;
- read all registers, and set one;
- set and clear an execution breakpoint;
- continue.

Note which registers hold the program counter, the return address, the function
arguments and the return value.

Always resume the CPU when you detach. An interrupted run leaves breakpoints set and
the game frozen, so keep a reset script that clears the known breakpoints and resumes.

## 2. Input and screenshots without window focus

**Input.** Find the routine that reads the controller and returns the button state,
and put a breakpoint right after the value is in its final form (for example after
the bits are inverted to "pressed = 1"). At the breakpoint, OR the button bits into the
return register, then continue. This works with the window unfocused or the desktop
locked.

- **Finding it:** search the code for the call into the system's input routine, or put
  breakpoints on candidates and keep the one that hits once per frame.
- **Frame clock:** if the input read runs once per frame (often in the vertical-blank
  interrupt), its breakpoint is a frame counter that runs without any input, and a
  regular place to stop the game.
- **Hold time:** hold a button for a few frames (4 here) and release it for a few.
  Some menus ignore shorter presses.

**Screenshots** from video memory, not from the window:
- If the debugger can read video memory, read the displayed framebuffer directly.
- If it cannot:
  1. Stop at the input breakpoint and save a scratch memory area and all registers.
  2. Write a tiny stub that calls the game's own "copy video memory to RAM" routine
     plus its "wait for the GPU" routine, and let it run.
  3. Read the pixels.
  4. Restore the memory and registers, so the game never notices.

  Graphics libraries often keep their function names in the binary, which helps find
  those routines.
- **The scratch area** must be memory that nothing uses. Prove it, for example by
  watching it stay unchanged over many frames.
- **Grab every framebuffer side by side.** With double buffering, the displayed one
  alternates.

## 3. Savestates offline

Write a reader for the emulator's savestate format. It is usually a header plus a
compressed blob holding main RAM and video memory. The emulator's own decompression
library can often be loaded directly.

Memory diffs between two states are the main way to find game structures:
1. Save just before a dialogue starts and just after.
2. Diff the RAM of the two states.
3. The interpreter's context is among the few words that changed into pointers.

## 4. Function tracing

Give the tracer a button press, a frame count and a list of candidate addresses. It
prints the first hits of each (address, caller) pair, with the argument registers and
the bytes at the first pointer argument.

This answers "which routine starts an event", "who prints this string" and "who calls
this every frame". Candidates come from the disassembly or from the code references
to a string.

## 5. Safe halt and game state

**Rewriting code in a running game crashes it** if a thread is executing inside that
code or will return into it. Here, a jump to a nonsense address was the symptom. Stop
the game only at a moment when no thread is in that code:
- Halt at a regular point, such as the input breakpoint.
- Read the state of every thread that was interrupted, not only the one that hit the
  breakpoint. The system's thread or context structures hold their saved program
  counter, return address and stack pointer.
- Reject the halt if any thread's program counter, its return address, or any word in
  the top of its stack (a few hundred bytes) points into the code you will rewrite.
  Then try the next frame, up to a few hundred frames, and report why if none is safe.
- Data that no running code holds a pointer into can be written at any halt.

**The script interpreter.** Most games run events through a bytecode interpreter with
a small context struct. Find these and write them down as named constants with
comments:
- the event number;
- the position and the read pointer;
- the "start" marker and its "none" value;
- the resume point;
- the enabled and busy flags;
- the script buffer address and its size.

An "idle" test (no block running, not busy, enabled) is what makes steps 6 and 7 safe.

## 6. Hot reload

A savestate made with an older build still runs the old program and the old data.
Write the new build into it, at a safe halt:

1. **Code and data the build adds outside the original program** (a variable-width
   font routine, a font, a string pool). If a boot stub copies them into place, parse
   the stub to get the (source, destination, size) list, so the hot reload copies
   exactly what boot would.
2. **The program.**
   - Write every byte that differs from the original program, plus every string slot
     and patch site the build may write, so a string that went back to its original
     form is rewritten too.
   - **Skip run-time buffers that overlay the program image** (graphics command
     buffers, heaps set up after boot). Writing them corrupts the running game; find
     them by comparing the loaded RAM with the file.
3. **File tables in RAM.** Rebuilt files move inside the disc or archive, and a stale
   table loads the wrong data.
4. **The loaded script.** Replace it with the built version of the same file, only while
   the interpreter is idle. Identify the file by its content shape, not by name.
5. **What cannot be written.** Data the game already copied into its own structures
   (names and tables of a running game). Document it; those need a new savestate.

The emulator must also run the new image, so files loaded later come from the new
build.

## 7. Scene preview

Goal: show any script unit (dialogue, caption, choice) in the running game now.

1. Take the unit's text ops from the **built** script, so they carry the build's text
   encoding (dictionary or compression).
2. Wrap them as one event block in the interpreter's block format (here: length, the
   ops, an end op).
3. Write the block to an **unused tail** of the script buffer. Check the buffer size
   against the largest script.
4. Breakpoint the routine that a scene's script tick calls to start or continue events.
   When it is hit with the interpreter context as argument and the interpreter idle:
   - point the read pointer at your block;
   - set the start marker;
   - continue.

   The game then runs the block with its own portraits, name boxes, paging and
   choices.
5. Some callers use the same routine only as a **query**. Inject only when the caller
   goes on to run the block: check the code after the return address for the call to
   the block runner.
6. Press the confirm button between pages and grab one screenshot per page until the
   interpreter is idle again.

Use only ops without side effects (text, captions, choices): no flags, units or items.
Then the scene is unchanged afterwards.

Lessons from building it:
- **Hook the routine with a breakpoint, not a heuristic.** Two attempts failed: guessing
  "inside the interpreter" from return addresses on the stack (it found stale values),
  and hooking a tick routine that does not run every frame.
- **The last confirm press can act in the scene.** Use a spot with nothing selected.
- **Blocks with branches play every variant in turn when flattened.** Document it.

## 8. Coverage check (complements the tools)

After a build, extract the built image and scan both the original and the built
files for runs of the game's text encoding. Compare the counts per file. Every
remaining run must be either a documented skip (debug or unused strings, listed with
the reason) or a bug.

**A missed case from this project.** Strings were missed because the extractor
accepted only part of the encoding: it rejected single-byte (half-width) characters.
- Make a new game's scanner accept the whole encoding from the start.
- When a scan finds something, check the code references around it, not only its
  first bytes: the real string can start a few bytes earlier.

Graphics, video and font files produce noise in the scanner. Compare their counts with
the original instead of reading them.

## 9. What to document per game

Write `docs/debug_tools.md` for the new game:
- a table of the tools;
- every address with its meaning:
  - the input read;
  - the thread state;
  - the interpreter fields;
  - the event start / run routines;
  - the scratch memory;
  - the buffers that must not be written;
- what hot reload cannot update;
- the list of savestates;
- the limits of the scene preview.

Keep the addresses as named constants with comments in one shared helper module. Add
a changelog entry for the tools.

## Checklist for a new game

- [ ] Portable emulator in the project, debugger on its own port, start/stop script.
- [ ] Debugger client: memory, registers, breakpoints; a reset script.
- [ ] Input breakpoint found and verified: it hits every frame and injected buttons work.
- [ ] Framebuffer capture (direct, or through the game's own copy routine), free scratch memory confirmed.
- [ ] Savestate reader; memory diffs used to find the interpreter context.
- [ ] Safe halt based on the state of every thread, tested by writing code while the game runs.
- [ ] Hot reload: added code/data, program diffs minus run-time buffers, file tables, idle script.
- [ ] Scene preview: event-start hook, query-caller filter, unused buffer tail.
- [ ] Coverage scan of the built image against the original.
- [ ] `docs/debug_tools.md` and the changelog written.
