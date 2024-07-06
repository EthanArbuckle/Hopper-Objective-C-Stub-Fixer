from typing import Optional


def read_c_string(doc: Document, address: int) -> str:
    """
    Read a null-terminated C string from the document at the given address.
    """
    result = bytearray()
    while True:
        byte = doc.readByte(address)
        if byte == 0:
            break
        result.append(byte)
        address += 1
    return result.decode()


def is_objc_stub(doc: Document, address: int) -> bool:
    """
    Check if the function at the given address is an Objective-C stub.
    """
    seg = doc.getCurrentSegment()
    instructions = [seg.getInstructionAtAddress(address + i * 4) for i in range(5)]
    if any(inst is None for inst in instructions):
        return False

    instruction_strings = [inst.getInstructionString() for inst in instructions]
    expected_instructions = ["adrp", "ldr", "adrp", "ldr", "br"]
    return all(inst.startswith(expected) for inst, expected in zip(instruction_strings, expected_instructions))


def parse_offset(ldr_inst_offset_str: str) -> Optional[int]:
    """
    Parse the offset from the ldr instruction string.
    """
    try:
        parts = ldr_inst_offset_str.split("[")[1].split("]")[0].split(",")
        offset = int(parts[1].strip()[1:], 16)
        return offset
    except (IndexError, ValueError) as e:
        print(f"Error parsing offset: {e}")
        return None


def get_page_address(adrp_inst: Instruction) -> Optional[int]:
    """
    Get the page address from the adrp instruction.
    """
    try:
        page_address = int(adrp_inst.getFormattedArgument(1)[1:], 16)
        return page_address
    except ValueError as e:
        print(f"Error parsing page address: {e}")
        return None


def get_selector(doc: Document, address: int) -> Optional[str]:
    """
    Extract the Objective-C selector from a stub function.
    """
    seg = doc.getCurrentSegment()
    adrp_inst = seg.getInstructionAtAddress(address)
    ldr_inst = seg.getInstructionAtAddress(address + 4)

    if not adrp_inst or not ldr_inst:
        print(f"Error: Couldn't read instructions at 0x{address:X} for selector extraction")
        return None

    page = get_page_address(adrp_inst)
    offset = parse_offset(str(ldr_inst.getFormattedArgument(1)))

    if page is None or offset is None:
        return None

    selector_addr = page + offset
    selector_ptr = doc.readUInt64LE(selector_addr)
    if selector_ptr:
        return read_c_string(doc, selector_ptr)

    return None


def rename_objc_stubs() -> None:
    """
    Main function to rename Objective-C stub functions in the current document.
    """
    doc = Document.getCurrentDocument()
    seg = doc.getSegmentByName("__TEXT")
    if not seg:
        print("Error: __TEXT segment not found")
        return

    renamed_functions = 0
    for procedure_address in seg.getNamedAddresses():
        procedure_name = doc.getNameAtAddress(procedure_address)
        if not procedure_name.startswith("sub_"):
            continue

        try:
            if not is_objc_stub(doc, procedure_address):
                continue

            selector = get_selector(doc, procedure_address)
            if not selector:
                print(f"Error: Failed to extract selector from stub at 0x{procedure_address:X} ({procedure_name})")
                continue
        except Exception as exc:
            print(f"Failed to analyze function 0x{procedure_address:X} ({procedure_name}): {exc}")
            continue

        new_procedure_name = f"{selector}()"
        print(f"Renaming stub at 0x{procedure_address:X} ({procedure_name}) to {new_procedure_name}")
        renamed_functions += 1
        doc.setNameAtAddress(procedure_address, new_procedure_name)

    print(f"Renamed {renamed_functions} stubs")


if __name__ == "__main__":
    rename_objc_stubs()
