"""Pure geometric helpers; millimetres throughout this module."""
import math


def solid_cells(solids, voids=()):
    boxes = list(solids) + list(voids)
    if not solids:
        return [[], [], []], set()
    axes = [sorted({b[a] for b in boxes} | {b[a + 3] for b in boxes}) for a in range(3)]
    indices = [{v: i for i, v in enumerate(axis)} for axis in axes]
    cells = set()
    for subtract, group in ((False, solids), (True, voids)):
        for b in group:
            if any(b[a] >= b[a + 3] for a in range(3)):
                raise ValueError('A solid needs positive dimensions')
            for i in range(indices[0][b[0]], indices[0][b[3]]):
                for j in range(indices[1][b[1]], indices[1][b[4]]):
                    for k in range(indices[2][b[2]], indices[2][b[5]]):
                        if subtract:
                            cells.discard((i, j, k))
                        else:
                            cells.add((i, j, k))
    return axes, cells


def boundary_mesh(solids, voids=()):
    axes, cells = solid_cells(solids, voids)
    vertices, faces, lookup = [], [], {}
    sides = [((-1, 0, 0), ((0,0,0),(0,0,1),(0,1,1),(0,1,0))),
             ((1, 0, 0), ((1,0,0),(1,1,0),(1,1,1),(1,0,1))),
             ((0,-1, 0), ((0,0,0),(1,0,0),(1,0,1),(0,0,1))),
             ((0, 1, 0), ((0,1,0),(0,1,1),(1,1,1),(1,1,0))),
             ((0, 0,-1), ((0,0,0),(0,1,0),(1,1,0),(1,0,0))),
             ((0, 0, 1), ((0,0,1),(1,0,1),(1,1,1),(0,1,1)))]
    for cell in sorted(cells):
        for direction, corners in sides:
            if tuple(cell[a] + direction[a] for a in range(3)) in cells:
                continue
            face = []
            for corner in corners:
                key = tuple(cell[a] + corner[a] for a in range(3))
                if key not in lookup:
                    lookup[key] = len(vertices)
                    vertices.append(tuple(axes[a][key[a]] for a in range(3)))
                face.append(lookup[key])
            faces.append(face)
    return vertices, faces


def within_tolerance(actual, expected, tolerance=1.0):
    return math.isfinite(actual) and math.isfinite(expected) and abs(actual - expected) <= tolerance + 1e-9


def door_pose(axis, low, high, wall_center, hinge, sign, degrees):
    pivot = high if hinge == 'high' else low
    position = (pivot, wall_center) if axis == 'x' else (wall_center, pivot)
    angle = (0 if axis == 'x' else 90) + (180 if hinge == 'high' else 0) + sign * degrees
    return position, angle
