from typing import List, Any, Optional

class UnicodeTable:
    @staticmethod
    def draw(headers: List[str], rows: List[List[Any]], alignments: Optional[List[str]] = None) -> str:
        if not rows:
            rows = [["" for _ in headers]]
            
        col_widths = []
        for i, h in enumerate(headers):
            max_w = len(str(h))
            for r in rows:
                max_w = max(max_w, len(str(r[i])))
            col_widths.append(max_w + 2)

        if not alignments:
            alignments = ["center"] * len(headers)

        def format_cell(val: Any, width: int, align: str) -> str:
            val_str = str(val)
            if align == "left":
                return f" {val_str:<{width-2}} "
            elif align == "right":
                return f" {val_str:>{width-2}} "
            else:
                return f" {val_str:^{width-2}} "

        top = "╒" + "╤".join("═" * w for w in col_widths) + "╕"
        hdr_line = "│" + "│".join(format_cell(h, col_widths[idx], alignments[idx]) for idx, h in enumerate(headers)) + "│"
        sep = "╞" + "╪".join("═" * w for w in col_widths) + "╡"
        
        row_lines = []
        for r in rows:
            r_line = "│" + "│".join(format_cell(r[idx], col_widths[idx], alignments[idx]) for idx, _ in enumerate(r)) + "│"
            row_lines.append(r_line)
            
        middle_sep = "├" + "┼".join("─" * w for w in col_widths) + "┤"
        body = f"\n{middle_sep}\n".join(row_lines)
        bottom = "╘" + "╧".join("═" * w for w in col_widths) + "╛"
        
        return f"{top}\n{hdr_line}\n{sep}\n{body}\n{bottom}"