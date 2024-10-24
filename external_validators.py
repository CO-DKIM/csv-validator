import hashlib


# Checksum for all known algorithms
def file_checksum(file_path, sum_type="md5"):
    # BUF_SIZE is totally arbitrary
    BUF_SIZE = 65536

    # Unknown hash algorithm, return prompt to user
    sum_type = sum_type.lower()
    if sum_type not in hashlib.algorithms_guaranteed:
        raise ValueError

    # Use the specified algorithm
    h = hashlib.new(sum_type)

    # Check the file exists
    try:
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                h.update(data)
    except FileNotFoundError:
        raise

    return h.hexdigest()
