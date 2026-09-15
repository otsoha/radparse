import logging
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
import numpy as np

format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=format)
logger = logging.getLogger(__name__)


@dataclass
class Data:
    mdata: list[str]
    headers: list[str]
    data: list[list[str]]


def validate_count(data: Data, search_str: str) -> bool:
    # check that line count matches the expected number of data points
    mdata = data.mdata
    for line in mdata:
        if search_str in line:
            line = line.strip()
            line = line.split("\t")
            n_points = line[1]
            logger.debug(f"Expected number of data points: {n_points}")
            if len(data.data) != int(n_points):
                return False

    return True


def absparse(lstream: Iterator[str], metadata_lines: int) -> Data:
    """Parse a stream of lines and return the next header line."""
    metadata = []
    # read the metadata lines somewhere if we happen to need them
    for _ in range(metadata_lines):
        line = next(lstream, None)
        if line is None:
            raise ValueError("Not enough metadata lines in the stream")
        line = line.strip()
        metadata.append(str(line))
        logger.debug(f"Metadata line: {metadata[-1]}")

    # next line should be the header line
    headers_line = next(lstream, None)
    if headers_line is None or not headers_line.strip():
        raise ValueError("No header line found after metadata lines")
    headers = headers_line.strip().split("\t")
    logger.debug(f"Headers: {headers}")

    # Lets gooooo data time!!!
    data = []
    num_headers = len(headers)
    for line in lstream:
        line = line.strip()  # strip newline
        if not line:
            logger.debug("Section end reached (blank line)")
            break

        data_line = line.split("\t")
        if len(data_line) != num_headers:
            raise ValueError(
                f"Data line has {len(data_line)} columns, expected {num_headers}: {data_line}"
            )
        data.append(data_line)
    logger.debug(f"Parsed {len(data)} data lines")
    return Data(metadata, headers, data)


def line_is_header(line: str) -> bool:
    """Check if a line is a header."""
    return line.startswith("[") and line.endswith("]")


def parse_LCChromatogram(lstream: Iterator[str]) -> Data:
    logger.debug("Parsing LC Chromatogram")
    # pass to absparse
    data = absparse(lstream, metadata_lines=6)
    if not validate_count(data, "# of Points"):
        raise ValueError(
            "Data line count in AD1 does not match expected number of points"
        )

    return data


def parse_PDAMultiChromatogram(lstream: Iterator[str]) -> Data:
    logger.debug("Parsing PDA Multi Chromatogram")
    # pass to absparse
    data = absparse(lstream, metadata_lines=9)
    if not validate_count(data, "# of Points"):
        raise ValueError(
            "Data line count in LC1 does not match expected number of points"
        )

    return data


HANDLERS = {
    "[LC Chromatogram(AD1)]": parse_LCChromatogram,
    "[PDA Multi Chromatogram(Ch1)]": parse_PDAMultiChromatogram,
}


def parse_file(data_path: Path) -> dict[str, Data]:
    results: dict[str, Data] = {}

    # read csv data
    with open(data_path, "r") as f:
        lstream = iter(f)

        for line in lstream:
            line = line.strip()
            if not line:
                continue  # skip blank lines

            if line_is_header(line):
                logger.debug(f"Header found: {line}")
                handler = HANDLERS.get(line)
                if handler is None:
                    logger.debug(f"No handler for header: {line}")
                    continue
                # parse the header
                results[line] = handler(lstream)
            else:
                # we only care about headers.
                pass
    return results


def main(data_path: Path) -> None:

    results = parse_file(data_path)

    # for now, we want a hardcoded output: First, AD1 and then ch1. Write to a single output file in
    op_path = data_path.with_name(data_path.stem + "_parsed.txt")
    delim = "\t"
    with open(op_path, "w") as f:
        ad1_data = results.get("[LC Chromatogram(AD1)]")
        ch1_data = results.get("[PDA Multi Chromatogram(Ch1)]")
        if ad1_data is None:
            raise ValueError("No data found for header: [LC Chromatogram(AD1)]")
        if ch1_data is None:
            raise ValueError("No data found for header: [PDA Multi Chromatogram(Ch1)]")

        # create a single header line
        ad1_headers = ad1_data.headers
        ch1_headers = ch1_data.headers
        combined_headers = ad1_headers + ch1_headers

        # empty rows for padding if we run out
        ad1_empty = [""] * len(ad1_data.headers)
        ch1_empty = [""] * len(ch1_data.headers)

        with open(op_path, "w") as f:
            f.write(delim.join(combined_headers) + "\n")
            for row_ad1, row_ch1 in zip_longest(ad1_data.data, ch1_data.data):
                # Use padded empty list if one section ended earlier than the other
                if row_ad1 is None:
                    row_ad1 = ad1_empty
                if row_ch1 is None:
                    row_ch1 = ch1_empty
                r1 = [str(val) for val in row_ad1]
                r2 = [str(val) for val in row_ch1]

                combined_row = r1 + r2
                f.write(delim.join(combined_row) + "\n")
        logger.info(f"Parsed data written to {op_path}")


def parse_and_write(sample_path: Path, blank_path: Path | None) -> str:
    """Parse the sample and blank files and write the output to a single file."""

    if not sample_path.exists():
        raise FileNotFoundError(f"Sample file not found: {sample_path}")

    if blank_path is not None and not blank_path.exists():
        raise FileNotFoundError(f"Blank file not found: {blank_path}")

    sample_results = parse_file(sample_path)
    blank_results = parse_file(blank_path) if blank_path else None

    # perform baseline correction if blank is provided
    if blank_results is not None:
        logger.info("Performing baseline correction using blank data")

        ad1_data_sample = sample_results.get("[LC Chromatogram(AD1)]").data
        ch1_data_sample = sample_results.get("[PDA Multi Chromatogram(Ch1)]").data
        ad1_data_blank = blank_results.get("[LC Chromatogram(AD1)]").data
        ch1_data_blank = blank_results.get("[PDA Multi Chromatogram(Ch1)]").data

        # unzip data into separate lists for each column
        ad1_sample_time, ad1_sample_intensity = zip(*ad1_data_sample)
        ch1_sample_time, ch1_sample_intensity = zip(*ch1_data_sample)
        ad1_blank_time, ad1_blank_intensity = zip(*ad1_data_blank)
        ch1_blank_time, ch1_blank_intensity = zip(*ch1_data_blank)

        # convert intensity values to float for subtraction, substitute , -> .
        ad1_sample_intensity = np.array(
            [float(i.replace(",", ".")) for i in ad1_sample_intensity]
        )
        ch1_sample_intensity = np.array(
            [float(i.replace(",", ".")) for i in ch1_sample_intensity]
        )
        ad1_blank_intensity = np.array(
            [float(i.replace(",", ".")) for i in ad1_blank_intensity]
        )
        ch1_blank_intensity = np.array(
            [float(i.replace(",", ".")) for i in ch1_blank_intensity]
        )

        # perform baseline correction by subtracting blank intensity from sample intensity
        ad1_sample_intensity = ad1_sample_intensity - ad1_blank_intensity
        ch1_sample_intensity = ch1_sample_intensity - ch1_blank_intensity

        # and finally, for the most perverted step: convert back to string and replace . -> ,
        ad1_sample_intensity = [str(i).replace(".", ",") for i in ad1_sample_intensity]
        ch1_sample_intensity = [str(i).replace(".", ",") for i in ch1_sample_intensity]

        # build back into data structure
        sample_results.get("[LC Chromatogram(AD1)]").data = list(
            zip(ad1_sample_time, ad1_sample_intensity)
        )
        sample_results.get("[PDA Multi Chromatogram(Ch1)]").data = list(
            zip(ch1_sample_time, ch1_sample_intensity)
        )

        # data uses
        logger.info("Baseline correction completed ")

    # for now, we want a hardcoded output: First, AD1 and then ch1. Write to a single output file in
    op_path = sample_path.with_name(sample_path.stem + "_parsed.txt")
    delim = "\t"
    with open(op_path, "w") as f:
        ad1_data = sample_results.get("[LC Chromatogram(AD1)]")
        ch1_data = sample_results.get("[PDA Multi Chromatogram(Ch1)]")
        if ad1_data is None:
            raise ValueError("No data found for header: [LC Chromatogram(AD1)]")
        if ch1_data is None:
            raise ValueError("No data found for header: [PDA Multi Chromatogram(Ch1)]")

        # create a single header line
        ad1_headers = ad1_data.headers
        ch1_headers = ch1_data.headers
        combined_headers = ad1_headers + ch1_headers

        # empty rows for padding if we run out
        ad1_empty = [""] * len(ad1_data.headers)
        ch1_empty = [""] * len(ch1_data.headers)

        with open(op_path, "w") as f:
            f.write(delim.join(combined_headers) + "\n")
            for row_ad1, row_ch1 in zip_longest(ad1_data.data, ch1_data.data):
                # Use padded empty list if one section ended earlier than the other
                if row_ad1 is None:
                    row_ad1 = ad1_empty
                if row_ch1 is None:
                    row_ch1 = ch1_empty
                r1 = [str(val) for val in row_ad1]
                r2 = [str(val) for val in row_ch1]

                combined_row = r1 + r2
                f.write(delim.join(combined_row) + "\n")
        logger.info(f"Parsed data written to {op_path}")
    return str(op_path), blank_path is not None


if __name__ == "__main__":
    print("Weasel Weasel Weasel")
