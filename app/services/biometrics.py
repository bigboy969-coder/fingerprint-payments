"""
FingerPay — Biometrics via DigitalPersona C SDK (Windows) or stubs (Linux/cloud).

On Windows (POS terminal): full capture, feature extraction, and matching via
DPFPApi.dll, dpHFtrEx.dll, dpHMatch.dll.

On Linux/cloud (Render): capture functions raise NotImplementedError — capture
happens on the Windows POS and templates are sent to the server as bytes.
The server only needs desc_to_blob/blob_to_desc for storage and verify() for
matching (verify also requires Windows for now).
"""
import ctypes
import platform
import threading

_WINDOWS = platform.system() == "Windows"

# ── Windows-only setup ────────────────────────────────────────────────────────
if _WINDOWS:
    from ctypes import wintypes
    import win32api
    import win32con
    import win32gui

    _dpfp = ctypes.WinDLL("DPFPApi.dll")
    _dpfx = ctypes.WinDLL("dpHFtrEx.dll")
    _dpmc = ctypes.WinDLL("dpHMatch.dll")

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_uint8 * 8)]

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]

    class _MC_SETTINGS(ctypes.Structure):
        _fields_ = [("numPreRegFeatures", ctypes.c_int)]

    _GUID_NULL = _GUID()

    _DP_PRIORITY_NORMAL   = 2
    _DP_SAMPLE_TYPE_IMAGE = 4
    _WN_COMPLETED         = 0
    _WM_DP_EVENT          = win32con.WM_USER + 100
    _FT_PRE_REG_FTR       = 0
    _FT_REG_FTR           = 1
    _FT_VER_FTR           = 2

    # DPFPApi
    _dpfp.DPFPInit.restype = ctypes.HRESULT
    _dpfp.DPFPTerm.restype = None
    _dpfp.DPFPCreateAcquisition.restype = ctypes.HRESULT
    _dpfp.DPFPCreateAcquisition.argtypes = [
        ctypes.c_uint32, ctypes.POINTER(_GUID), ctypes.c_uint32,
        wintypes.HWND, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    _dpfp.DPFPStartAcquisition.restype  = ctypes.HRESULT
    _dpfp.DPFPStartAcquisition.argtypes = [ctypes.c_uint32]
    _dpfp.DPFPStopAcquisition.restype   = ctypes.HRESULT
    _dpfp.DPFPStopAcquisition.argtypes  = [ctypes.c_uint32]
    _dpfp.DPFPDestroyAcquisition.restype  = ctypes.HRESULT
    _dpfp.DPFPDestroyAcquisition.argtypes = [ctypes.c_uint32]
    _dpfp.DPFPBufferFree.argtypes = [ctypes.c_void_p]

    # dpHFtrEx
    _dpfx.FX_init.restype = ctypes.c_int
    _dpfx.FX_createContext.restype = ctypes.c_int
    _dpfx.FX_createContext.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    _dpfx.FX_closeContext.restype = ctypes.c_int
    _dpfx.FX_closeContext.argtypes = [ctypes.c_void_p]
    _dpfx.FX_getFeaturesLen.restype = ctypes.c_int
    _dpfx.FX_getFeaturesLen.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int),
                                         ctypes.POINTER(ctypes.c_int)]
    _dpfx.FX_extractFeatures.restype = ctypes.c_int
    _dpfx.FX_extractFeatures.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
        ctypes.c_int, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int)]

    # dpHMatch
    _dpmc.MC_init.restype = ctypes.c_int
    _dpmc.MC_createContext.restype = ctypes.c_int
    _dpmc.MC_createContext.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    _dpmc.MC_closeContext.restype = ctypes.c_int
    _dpmc.MC_closeContext.argtypes = [ctypes.c_void_p]
    _dpmc.MC_getSettings.restype = ctypes.c_int
    _dpmc.MC_getSettings.argtypes = [ctypes.POINTER(_MC_SETTINGS)]
    _dpmc.MC_getFeaturesLen.restype = ctypes.c_int
    _dpmc.MC_getFeaturesLen.argtypes = [ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    _dpmc.MC_generateRegFeatures.restype = ctypes.c_int
    _dpmc.MC_generateRegFeatures.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    _dpmc.MC_verifyFeaturesEx.restype = ctypes.c_int
    _dpmc.MC_verifyFeaturesEx.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int)]

    # Init
    _dpfp.DPFPInit()
    _dpfx.FX_init()
    _dpmc.MC_init()

    _s = _MC_SETTINGS()
    _dpmc.MC_getSettings(ctypes.byref(_s))
    SCANS_NEEDED = _s.numPreRegFeatures

    _er = ctypes.c_int(0)
    _vr = ctypes.c_int(0)
    _tr = ctypes.c_int(0)
    _dpfx.FX_getFeaturesLen(_FT_PRE_REG_FTR, ctypes.byref(_er), None)
    _dpfx.FX_getFeaturesLen(_FT_VER_FTR,     ctypes.byref(_vr), None)
    _dpmc.MC_getFeaturesLen(_FT_REG_FTR, 0,  ctypes.byref(_tr), None)

    ENROLL_FEATURE_SIZE = _er.value
    VERIFY_FEATURE_SIZE = _vr.value
    TEMPLATE_SIZE       = _tr.value

    _wc_counter = 0

else:
    # Linux/cloud stubs — values are not used for capture but needed for imports
    SCANS_NEEDED        = 4
    ENROLL_FEATURE_SIZE = 318
    VERIFY_FEATURE_SIZE = 318
    TEMPLATE_SIZE       = 1632


# ── Internal helpers (Windows only) ──────────────────────────────────────────

def _capture_one_image(timeout: int = 15) -> tuple[bytes, int]:
    if not _WINDOWS:
        raise NotImplementedError("Fingerprint capture requires a Windows POS terminal.")
    global _wc_counter
    _wc_counter += 1

    result: dict = {"data": None}
    h_op   = ctypes.c_uint32(0)
    main_id = win32api.GetCurrentThreadId()

    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == _WM_DP_EVENT and wparam == _WN_COMPLETED:
            blob = _DATA_BLOB.from_address(lparam)
            img  = (ctypes.c_uint8 * blob.cbData).from_address(blob.pbData)
            result["data"] = (bytes(img), blob.cbData)
            win32api.PostThreadMessage(main_id, win32con.WM_QUIT, 0, 0)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    class_name = f"DPCapWnd{_wc_counter}"
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = class_name
    wc.lpfnWndProc   = wnd_proc
    win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(
        class_name, "FingerPay", win32con.WS_OVERLAPPEDWINDOW,
        200, 200, 280, 60, 0, 0, 0, None)
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    win32gui.SetForegroundWindow(hwnd)

    _dpfp.DPFPCreateAcquisition(
        _DP_PRIORITY_NORMAL, ctypes.byref(_GUID_NULL),
        _DP_SAMPLE_TYPE_IMAGE, hwnd, _WM_DP_EVENT, ctypes.byref(h_op))
    _dpfp.DPFPStartAcquisition(h_op.value)

    import time
    timer_fired = threading.Event()

    def _timeout():
        time.sleep(timeout)
        if not timer_fired.is_set():
            win32api.PostThreadMessage(main_id, win32con.WM_QUIT, 0, 0)

    threading.Thread(target=_timeout, daemon=True).start()
    win32gui.PumpMessages()
    timer_fired.set()

    _dpfp.DPFPStopAcquisition(h_op.value)
    _dpfp.DPFPDestroyAcquisition(h_op.value)
    win32gui.DestroyWindow(hwnd)

    if result["data"] is None:
        raise TimeoutError("No finger detected within timeout period.")
    return result["data"]


def _extract_features(image_bytes: bytes, image_size: int, purpose: int, feature_size: int) -> bytes | None:
    fx_ctx = ctypes.c_void_p(0)
    _dpfx.FX_createContext(ctypes.byref(fx_ctx))
    img_buf  = (ctypes.c_uint8 * image_size)(*image_bytes)
    feat_buf = (ctypes.c_uint8 * feature_size)()
    img_q = ctypes.c_int(0)
    ftr_q = ctypes.c_int(0)
    created = ctypes.c_int(0)
    _dpfx.FX_extractFeatures(
        fx_ctx.value, image_size, img_buf, purpose,
        feature_size, feat_buf,
        ctypes.byref(img_q), ctypes.byref(ftr_q), ctypes.byref(created))
    _dpfx.FX_closeContext(fx_ctx.value)
    return bytes(feat_buf) if created.value else None


# ── Public API ────────────────────────────────────────────────────────────────

def capture_enrollment_features(timeout: int = 15) -> bytes:
    """Capture one enrollment scan. Windows POS only."""
    image_bytes, image_size = _capture_one_image(timeout)
    features = _extract_features(image_bytes, image_size, _FT_PRE_REG_FTR, ENROLL_FEATURE_SIZE)
    if features is None:
        raise ValueError("Fingerprint quality too poor for enrollment. Try again.")
    return features


def capture_verification_features(timeout: int = 15) -> bytes:
    """Capture one verification scan. Windows POS only."""
    image_bytes, image_size = _capture_one_image(timeout)
    features = _extract_features(image_bytes, image_size, _FT_VER_FTR, VERIFY_FEATURE_SIZE)
    if features is None:
        raise ValueError("Fingerprint quality too poor. Try again.")
    return features


def enrollment_features_needed(feature_blobs: list[bytes]) -> int:
    """How many more enrollment scans are needed."""
    return max(0, SCANS_NEEDED - len(feature_blobs))


def build_template(feature_blobs: list[bytes]) -> bytes:
    """Build enrollment template from feature blobs. Windows POS only."""
    if not _WINDOWS:
        raise NotImplementedError("Template building requires a Windows POS terminal.")
    mc_ctx = ctypes.c_void_p(0)
    _dpmc.MC_createContext(ctypes.byref(mc_ctx))
    feat_bufs = [(ctypes.c_uint8 * len(f))(*f) for f in feature_blobs]
    feat_ptrs = (ctypes.c_void_p * len(feature_blobs))()
    for i, buf in enumerate(feat_bufs):
        feat_ptrs[i] = ctypes.cast(buf, ctypes.c_void_p)
    tmpl_buf = (ctypes.c_uint8 * TEMPLATE_SIZE)()
    created  = ctypes.c_int(0)
    rc = _dpmc.MC_generateRegFeatures(
        mc_ctx.value, 0, len(feature_blobs),
        ENROLL_FEATURE_SIZE, feat_ptrs,
        TEMPLATE_SIZE, tmpl_buf, None, ctypes.byref(created))
    _dpmc.MC_closeContext(mc_ctx.value)
    if not created.value:
        raise ValueError(f"Template generation failed (rc={rc}). Enroll again.")
    return bytes(tmpl_buf)


def verify(verification_features_blob: bytes, template_blob: bytes) -> bool:
    """1:1 match of verification features against a stored template. Windows POS only."""
    if not _WINDOWS:
        raise NotImplementedError("Fingerprint matching requires a Windows POS terminal.")
    mc_ctx = ctypes.c_void_p(0)
    _dpmc.MC_createContext(ctypes.byref(mc_ctx))
    ver_buf  = (ctypes.c_uint8 * len(verification_features_blob))(*verification_features_blob)
    tmpl_buf = (ctypes.c_uint8 * len(template_blob))(*template_blob)
    far      = ctypes.c_double(0)
    decision = ctypes.c_int(0)
    _dpmc.MC_verifyFeaturesEx(
        mc_ctx.value,
        len(template_blob), tmpl_buf,
        len(verification_features_blob), ver_buf,
        0, None, None, None,
        ctypes.byref(far), ctypes.byref(decision))
    _dpmc.MC_closeContext(mc_ctx.value)
    return bool(decision.value)


def desc_to_blob(data: bytes) -> bytes:
    return data


def blob_to_desc(data: bytes) -> bytes:
    return data
