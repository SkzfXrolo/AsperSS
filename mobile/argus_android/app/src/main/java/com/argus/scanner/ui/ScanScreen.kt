package com.argus.scanner.ui

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.argus.scanner.core.ScanOrchestrator
import com.argus.scanner.core.ScanProgressEvent
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * ScanScreen — UI principal de la APK Argus Android.
 *
 * Estados del flujo:
 *   - Onboarding (si faltan permisos)
 *   - Input (token + botón scan)
 *   - Running (log en vivo)
 *   - Done (risk score + verdict + link al panel)
 */

private val Bronze      = Color(0xFFB48A62)
private val BronzeLight = Color(0xFFEAD8C0)
private val BgDark      = Color(0xFF15110A)
private val BgCard      = Color(0xFF1F1810)
private val TextDim     = Color(0xFF8E7B65)
private val Clean       = Color(0xFF5BC180)
private val Warn        = Color(0xFFFFB86B)
private val Danger      = Color(0xFFFF6B6B)

@Composable
fun ScanScreen(
    initialToken: String,
    hasStorage: () -> Boolean,
    hasUsage: () -> Boolean,
    requestStorage: () -> Unit,
    requestUsage: () -> Unit,
    requestScreenshotConsent: ((Int, Intent?) -> Unit) -> Unit = { it(0, null) },
    getPendingScreenshot: () -> Pair<Int, Intent?> = { 0 to null },
    clearScreenshot: () -> Unit = {},
) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()

    var token by rememberSaveable { mutableStateOf(initialToken) }
    var phase by rememberSaveable { mutableStateOf(if (initialToken.isNotBlank()) "input" else "onboarding") }
    val log = remember { mutableStateListOf<String>() }
    var riskScore by rememberSaveable { mutableStateOf(-1) }
    var verdict by rememberSaveable { mutableStateOf("") }
    var scanId by rememberSaveable { mutableStateOf(0L) }
    var error by rememberSaveable { mutableStateOf<String?>(null) }
    var screenshotEnabled by rememberSaveable { mutableStateOf(true) }

    // Re-evaluar permisos cuando volvamos al foreground.
    var storageGranted by remember { mutableStateOf(hasStorage()) }
    var usageGranted   by remember { mutableStateOf(hasUsage()) }
    LaunchedEffect(phase) {
        storageGranted = hasStorage()
        usageGranted   = hasUsage()
    }

    fun launchScan(includeScreenshot: Boolean) {
        error = null
        log.clear()
        phase = "running"
        val orch = ScanOrchestrator(ctx)
        val (rc, data) = if (includeScreenshot) getPendingScreenshot() else (0 to null)
        scope.launch {
            try {
                orch.run(token, rc, data).collectLatest { ev ->
                    when (ev) {
                        is ScanProgressEvent.Log -> log.add(ev.line)
                        is ScanProgressEvent.ScanCreated -> scanId = ev.scanId
                        is ScanProgressEvent.Done -> {
                            riskScore = ev.riskScore
                            verdict = ev.verdict
                            phase = "done"
                            clearScreenshot()
                        }
                        is ScanProgressEvent.Failed -> {
                            error = ev.message
                            phase = "input"
                            clearScreenshot()
                        }
                    }
                }
            } catch (e: Exception) {
                error = e.message ?: "Error desconocido"
                phase = "input"
                clearScreenshot()
            }
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = BgDark) {
        when (phase) {
            "onboarding" -> OnboardingPanel(
                storageGranted = storageGranted,
                usageGranted   = usageGranted,
                onRequestStorage = { requestStorage(); storageGranted = hasStorage() },
                onRequestUsage   = { requestUsage();   usageGranted   = hasUsage() },
                onRecheck = {
                    storageGranted = hasStorage()
                    usageGranted   = hasUsage()
                },
                onContinue = { phase = "input" }
            )
            "input" -> InputPanel(
                token = token,
                onTokenChange = { token = it },
                screenshotEnabled = screenshotEnabled,
                onScreenshotToggle = { screenshotEnabled = it },
                onStart = {
                    if (screenshotEnabled) {
                        // Pedir consent y luego arrancar (con screenshot si OK).
                        requestScreenshotConsent { rc, data ->
                            // El callback ya guardó el resultado en MainActivity;
                            // launch usa getPendingScreenshot que ahora tiene
                            // los valores correctos.
                            launchScan(includeScreenshot = (data != null))
                        }
                    } else {
                        launchScan(includeScreenshot = false)
                    }
                },
                error = error
            )
            "running" -> RunningPanel(log = log)
            "done" -> DonePanel(
                riskScore = riskScore,
                verdict = verdict,
                scanId = scanId,
                onRunAgain = {
                    riskScore = -1
                    verdict = ""
                    log.clear()
                    phase = "input"
                }
            )
        }
    }
}

// ─────────────────────────── Onboarding ───────────────────────────

@Composable
private fun OnboardingPanel(
    storageGranted: Boolean,
    usageGranted: Boolean,
    onRequestStorage: () -> Unit,
    onRequestUsage: () -> Unit,
    onRecheck: () -> Unit,
    onContinue: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            Text(
                "ARGUS",
                color = BronzeLight,
                fontSize = 30.sp,
                fontWeight = FontWeight.Black,
            )
            Text(
                "All-Seeing · Always Watching",
                color = Bronze,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.height(20.dp))
            Text(
                "Permisos requeridos",
                color = BronzeLight, fontSize = 22.sp, fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(6.dp))
            Text(
                "Solo lo mínimo necesario. NO pedimos contactos, mic, " +
                        "cámara, ubicación, SMS ni accesibilidad.",
                color = TextDim, fontSize = 14.sp,
            )
            Spacer(Modifier.height(20.dp))

            PermissionCard(
                title = "Acceso a archivos",
                desc = "Para revisar carpetas de Minecraft Bedrock y de PojavLauncher en /sdcard.",
                granted = storageGranted,
                onClick = onRequestStorage,
            )
            Spacer(Modifier.height(12.dp))
            PermissionCard(
                title = "Acceso al uso de apps",
                desc = "Para detectar qué cheat clients fueron lanzados recientemente. " +
                        "Concedelo en Ajustes ▸ Acceso especial.",
                granted = usageGranted,
                onClick = onRequestUsage,
            )
            Spacer(Modifier.height(12.dp))
            PermissionCard(
                title = "Lista de apps instaladas",
                desc = "Otorgado automáticamente al instalar (QUERY_ALL_PACKAGES).",
                granted = true,
                onClick = null,
            )
        }

        Column {
            TextButton(onClick = onRecheck) {
                Text("Reverificar permisos", color = Bronze)
            }
            Spacer(Modifier.height(8.dp))
            Button(
                onClick = onContinue,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Bronze,
                    contentColor = BgDark,
                    disabledContainerColor = Bronze.copy(alpha = 0.3f),
                    disabledContentColor = TextDim,
                ),
                enabled = storageGranted && usageGranted,
                shape = RoundedCornerShape(12.dp),
            ) {
                Text("Continuar", fontWeight = FontWeight.Bold, fontSize = 15.sp)
            }
        }
    }
}

@Composable
private fun PermissionCard(
    title: String,
    desc: String,
    granted: Boolean,
    onClick: (() -> Unit)?,
) {
    val borderColor = if (granted) Clean.copy(alpha = 0.5f) else Bronze.copy(alpha = 0.4f)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(BgCard, RoundedCornerShape(12.dp))
            .border(1.dp, borderColor, RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = BronzeLight, fontWeight = FontWeight.Bold, fontSize = 14.sp)
            Spacer(Modifier.height(2.dp))
            Text(desc, color = TextDim, fontSize = 12.sp)
        }
        Spacer(Modifier.width(8.dp))
        if (granted) {
            Text("✓", color = Clean, fontSize = 22.sp, fontWeight = FontWeight.Black)
        } else if (onClick != null) {
            Button(
                onClick = onClick,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Bronze.copy(alpha = 0.18f),
                    contentColor = BronzeLight,
                ),
                shape = RoundedCornerShape(10.dp),
            ) { Text("Otorgar", fontSize = 12.sp) }
        }
    }
}

// ─────────────────────────── Input ───────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun InputPanel(
    token: String,
    onTokenChange: (String) -> Unit,
    screenshotEnabled: Boolean,
    onScreenshotToggle: (Boolean) -> Unit,
    onStart: () -> Unit,
    error: String?,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            Text("ARGUS", color = BronzeLight, fontSize = 30.sp, fontWeight = FontWeight.Black)
            Text("All-Seeing · Always Watching", color = Bronze, fontSize = 13.sp)
            Spacer(Modifier.height(28.dp))
            Text("Iniciar scan", color = BronzeLight, fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text(
                "Pegá el token que el staff te compartió. El scan tarda " +
                        "alrededor de 30 segundos y se sube automáticamente al panel.",
                color = TextDim, fontSize = 13.sp,
            )
            Spacer(Modifier.height(18.dp))
            OutlinedTextField(
                value = token,
                onValueChange = onTokenChange,
                placeholder = { Text("Pegá tu token aquí…", color = TextDim) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Ascii,
                    imeAction = ImeAction.Done,
                ),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Bronze,
                    unfocusedBorderColor = Bronze.copy(alpha = 0.4f),
                    focusedTextColor = BronzeLight,
                    unfocusedTextColor = BronzeLight,
                    cursorColor = BronzeLight,
                ),
                shape = RoundedCornerShape(10.dp),
            )
            if (!error.isNullOrBlank()) {
                Spacer(Modifier.height(10.dp))
                Text(error, color = Danger, fontSize = 12.sp)
            }

            Spacer(Modifier.height(20.dp))
            ScreenshotToggleRow(
                enabled = screenshotEnabled,
                onToggle = onScreenshotToggle,
            )
        }

        Button(
            onClick = onStart,
            modifier = Modifier.fillMaxWidth().height(54.dp),
            enabled = token.length >= 8,
            colors = ButtonDefaults.buttonColors(
                containerColor = Bronze,
                contentColor = BgDark,
                disabledContainerColor = Bronze.copy(alpha = 0.3f),
                disabledContentColor = TextDim,
            ),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text("Iniciar scan", fontWeight = FontWeight.Black, fontSize = 16.sp)
        }
    }
}

@Composable
private fun ScreenshotToggleRow(
    enabled: Boolean,
    onToggle: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(BgCard, RoundedCornerShape(12.dp))
            .border(1.dp, Bronze.copy(alpha = 0.4f), RoundedCornerShape(12.dp))
            .clickable { onToggle(!enabled) }
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                "Adjuntar screenshot",
                color = BronzeLight, fontWeight = FontWeight.Bold, fontSize = 14.sp,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                if (enabled)
                    "Argus pedirá permiso para capturar pantalla al iniciar."
                else
                    "Solo se subirán los hallazgos de archivos y apps.",
                color = TextDim, fontSize = 12.sp,
            )
        }
        Spacer(Modifier.width(8.dp))
        Switch(
            checked = enabled,
            onCheckedChange = onToggle,
            colors = SwitchDefaults.colors(
                checkedThumbColor = BronzeLight,
                checkedTrackColor = Bronze,
                uncheckedThumbColor = TextDim,
                uncheckedTrackColor = BgCard,
                uncheckedBorderColor = Bronze.copy(alpha = 0.5f),
            ),
        )
    }
}

// ─────────────────────────── Running ───────────────────────────

@Composable
private fun RunningPanel(log: List<String>) {
    val listState = rememberLazyListState()
    LaunchedEffect(log.size) {
        if (log.isNotEmpty()) listState.animateScrollToItem(log.size - 1)
    }
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
    ) {
        Text("Escaneando…", color = BronzeLight, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Text("Revisando paquetes, archivos y signals.", color = TextDim, fontSize = 13.sp)
        Spacer(Modifier.height(18.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .background(BgCard, RoundedCornerShape(10.dp))
                .border(1.dp, Bronze.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            LazyColumn(state = listState) {
                items(log) { line ->
                    val color = when {
                        line.startsWith("[!]") -> Warn
                        line.startsWith("[CRIT]") -> Danger
                        line.startsWith("[OK]") -> Clean
                        else -> BronzeLight
                    }
                    Text(
                        line,
                        color = color,
                        fontSize = 11.sp,
                        modifier = Modifier.padding(vertical = 1.dp),
                    )
                }
            }
        }
    }
}

// ─────────────────────────── Done ───────────────────────────

@Composable
private fun DonePanel(
    riskScore: Int,
    verdict: String,
    scanId: Long,
    onRunAgain: () -> Unit,
) {
    val (verdictColor, verdictTitle) = when {
        riskScore >= 70 -> Danger to "HACK"
        riskScore >= 30 -> Warn   to "SOSPECHOSO"
        else            -> Clean  to "LIMPIO"
    }
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(60.dp))
            Text("ARGUS", color = BronzeLight, fontSize = 28.sp, fontWeight = FontWeight.Black)
            Text("Scan completado", color = Bronze, fontSize = 13.sp)
            Spacer(Modifier.height(40.dp))
            Box(
                modifier = Modifier
                    .size(180.dp)
                    .background(verdictColor.copy(alpha = 0.12f), RoundedCornerShape(percent = 50))
                    .border(3.dp, verdictColor, RoundedCornerShape(percent = 50)),
                contentAlignment = Alignment.Center,
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        "${riskScore.coerceAtLeast(0)}",
                        color = verdictColor,
                        fontSize = 64.sp,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        "RISK SCORE",
                        color = TextDim, fontSize = 10.sp,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
            Spacer(Modifier.height(24.dp))
            Text(
                verdictTitle,
                color = verdictColor, fontSize = 30.sp,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(6.dp))
            if (verdict.isNotBlank()) {
                Text(verdict, color = TextDim, fontSize = 13.sp, textAlign = TextAlign.Center)
            }
            Spacer(Modifier.height(14.dp))
            if (scanId > 0) {
                Text(
                    "Scan #$scanId · subido al panel",
                    color = Bronze, fontSize = 12.sp, fontWeight = FontWeight.Medium,
                )
            }
        }

        Button(
            onClick = onRunAgain,
            modifier = Modifier.fillMaxWidth().height(50.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Bronze,
                contentColor = BgDark,
            ),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text("Hacer otro scan", fontWeight = FontWeight.Bold, fontSize = 15.sp)
        }
    }
}
