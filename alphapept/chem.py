# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_chem.ipynb (unless otherwise specified).

__all__ = ['IsotopeDistribution', 'fast_add', 'numba_bin', 'dict_to_dist', 'spec', 'get_average_formula',
           'mass_to_dist', 'calculate_mass', 'M_PROTON']

# Cell

import numpy as np
from numba import int32, float32, float64, njit, types
from numba.experimental import jitclass
from numba.typed import Dict

spec = [
    ('m0', float32),
    ('dm', int32),
    ('intensities', float64[:]),
]

@jitclass(spec)
class IsotopeDistribution:
    """
    Class to calculate Isotope Distributions.
    Members:
        self.m0: the mono-isotopic mass
        self.dm: number of isotopes
        self.intensities: isotope patterns
    """
    def __init__(self):

        self.m0 = 0
        self.dm = 1
        self.intensities = np.array([1.0])

    def add(self, x)->None:
        """
        Convolute self with the other IsotopeDistribution
        Args:
            x (IsotopeDistribution): the other object to be convoluted with self.
        Returns:
            None. self.m0, self.dm and self.intensities will be updated inplace.
        """
        self.m0, self.dm, self.intensities = fast_add(
            self.m0, self.dm, self.intensities, x.m0, x.dm, x.intensities
        )

    def add_from_dict(self, x)->None:
        """
        Convolute self with a np.ndarray
        Args:
            x (np.ndarray:float): the np.ndarray to be convoluted. x[0] is the m0, x[1] is the dm, and x[2:] is the intensity pattern
        Returns:
            None. self.m0, self.dm and self.intensities will be updated inplace.
        """
        self.m0, self.dm, self.intensities = fast_add(
            self.m0, self.dm, self.intensities, x[0], np.int(x[1]), x[2:]
        )

    def copy(self):
        """
        Copy this instance
        """
        i = IsotopeDistribution()
        i.m0 = self.m0
        i.dm = self.dm
        i.intensities = self.intensities

        return i

    def mult(self, n):
        """
        Convolute this instance for n times. Using "binary search"-like strategy to accelerate the convolution.
        Args:
            n (int): how many times to convolute this instance
        Returns:
            IsotopeDistribution:
        """
        binary = numba_bin(n)

        if n == 1:
            return self.copy()
        else:
            i = IsotopeDistribution()

            multiples = self.copy()

            for count in binary[::-1]:
                if count == 1:
                    i.add(multiples)
                multiples.add(multiples)

            return i


@njit
def fast_add(m0, dm0, int0, m1, dm1, int1, PRUNE_LEVEL=0.000001):
    """
    Convolute two isotope distributions
    Args:
        m0 (float): the mono-isotopic mass of the first isotope distribution.
        dm0 (int): the number of isotope intensities in the first isotope distribution.
        int0 (np.ndarray:float): the intensity pattern of the first isotope distribution.
        m1 (float): the mono-isotopic mass of the second isotope distribution.
        dm1 (int): the number of isotope intensities in the second isotope distribution.
        int1 (np.ndarray:float): the intensity pattern of the second isotope distribution.
        PRUNE_LEVEL: relative intensity below this value will be discarded.
    Returns:
        tuple of (float, int, np.ndarray): the updated isotope distributions
    """

    m0 += m1

    ni = np.zeros(dm0 + dm1 - 1)
    for i in range(dm0):
        for j in range(dm1):
            ni[i + j] += int0[i] * int1[j]

    dm0 += dm1 - 1

    int0 = ni / np.max(ni)

    while ni[dm0 - 1] < PRUNE_LEVEL:
        dm0 -= 1

    return m0, dm0, int0

@njit
def numba_bin(decimal:int)->list:
    """
    Numba compatibale function to convert decimal to binary as a list
    """

    binary = []

    while decimal != 0:
        bit = int(decimal % 2)
        binary.insert(0,bit)
        decimal = int(decimal/2)

    return binary

@njit
def dict_to_dist(
    counted_AA:Dict,
    isotopes:Dict)->IsotopeDistribution:
    """
    Function to convert a dictionary with numbers of amino acids to a isotope distribution.
    Args:
        counted_AA (numba.typed.Dict): key is the chemical element and value is the element number.
        isotopes (numba.typed.Dict): key is the chemical element and the value is the alphapept.constants.isotopes

    Returns:
        IsotopeDistribution: isotope distribution with m0 and intensites.
    """
    dist = IsotopeDistribution()
    for AA in counted_AA.keys():

        x = IsotopeDistribution()
        x.add(isotopes[AA])
        x = x.mult(counted_AA[AA])

        dist.add(x)

    return dist

# Cell
from numba.typed import Dict
from numba import types, njit
from .constants import averagine_avg

@njit
def get_average_formula(molecule_mass, averagine_aa, isotopes, sulphur=True):
    """
    Function to calculate the averagine formula for a molecule mass.
    Args:
        molecule_mass (float): the peptide mass to calculate the averagine.
        averagine_aa (dict): the averagine chemical compositions. See alphapept.constants.averagine_aa.
        isotopes (dict): the isotope patterns for each chemical element. See alphapept.constants.isotopes.
        sulphur (bool): Mode w/o sulphur is not implemented yet.
    Returns:
        dict: the averagine chemical compositions for the given molecule_mass
    """

    if sulphur:
        averagine_units = molecule_mass / averagine_avg
    else:
        raise NotImplementedError("Mode w/o sulphur is not implemented yet")

    counted_AA = Dict.empty(key_type=types.unicode_type, value_type=types.int64)

    final_mass = 0

    # Calculate integral mnumbers of atoms
    for AA in averagine_aa.keys():
        counted_AA[AA] = int(np.round(averagine_units * averagine_aa[AA]))
        final_mass += counted_AA[AA] * isotopes[AA].m0

    # Correct with H atoms
    h_correction = int(np.round((molecule_mass - final_mass) / isotopes["H"].m0))
    counted_AA["H"] += h_correction

    return counted_AA

# Cell
@njit
def mass_to_dist(molecule_mass, averagine_aa, isotopes):
    """
    Function to calculate an isotope distribution from a molecule mass using the averagine model.
    """
    counted_AA = get_average_formula(molecule_mass, averagine_aa, isotopes)

    dist = dict_to_dist(counted_AA, isotopes)

    masses = np.array([dist.m0 + i for i in range(len(dist.intensities))])
    ints = dist.intensities

    return masses, ints

# Cell
from .constants import mass_dict

M_PROTON = mass_dict['Proton']

@njit
def calculate_mass(mono_mz, charge):
    """
    Calculate the precursor mass from mono mz and charge
    """
    prec_mass = mono_mz * abs(charge) - charge * M_PROTON

    return prec_mass