import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// 1. പ്ലാനുകളുടെ വിവരങ്ങൾ സൂക്ഷിക്കാനുള്ള ഡാറ്റാ ക്ലാസ്സ്
data class Plan(
    val title: String,
    val price: String,
    val features: List<String>,
    val icon: String
)

@Composable
fun VLXApp(modifier: Modifier = Modifier) {
    
    // 2. ചിത്രത്തിൽ കാണുന്ന അതേ പ്ലാനുകളുടെ ലിസ്റ്റ് (Data List)
    val plans = listOf(
        Plan(title = "WhatsApp Plan", price = "₹500", features = listOf("Promotion in WhatsApp groups", "Fast reach"), icon = "💬"),
        Plan(title = "YouTube (3 Channels)", price = "₹2500", features = listOf("Short video promotion"), icon = "📺"),
        Plan(title = "YouTube (4 Channels)", price = "₹3000", features = listOf("Short video promotion"), icon = "📺"),
        Plan(title = "YouTube (5 Channels)", price = "₹3500", features = listOf("Short video promotion"), icon = "📺"),
        Plan(title = "Premium Plan", price = "₹5500", features = listOf("Long + Short video", "Max reach"), icon = "👑"),
        Plan(title = "Combo Plan", price = "₹2800", features = listOf("WhatsApp + YouTube", "Fast promotion"), icon = "💎"),
        Plan(title = "Advanced Combo", price = "₹4000", features = listOf("WhatsApp + YouTube", "Fast promotion", "Extra Ads"), icon = "🔥"),
        Plan(title = "Business Plan", price = "₹10,000", features = listOf("Monthly plan", "30 ads", "Priority support"), icon = "💼")
    )

    // 3. ചിത്രത്തിൽ കാണുന്നതുപോലെയുള്ള ബാക്ക്ഗ്രൗണ്ട് ഗ്രേഡിയന്റ് കളർ സെറ്റിംഗ്സ്
    val backgroundGradient = Brush.verticalGradient(
        colors = listOf(
            Color(0xFF6A11CB), // കടും നീല/പർപ്പിൾ ഷേഡ്
            Color(0xFF2575FC)  // ലൈറ്റ് ബ്ലൂ ഷേഡ്
        )
    )

    // 4. മെയിൻ ലേഔട്ട് ഡിസൈൻ
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(backgroundGradient)
            .padding(16.dp)
    ) {
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                Text(
                    text = "Available Plans",
                    color = Color.White,
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
            }
            
            // ലിസ്റ്റിലുള്ള ഓരോ പ്ലാനും ഡിസൈൻ കാർഡുകളാക്കി മാറ്റുന്നു
            items(plans) { plan ->
                PlanCard(plan = plan)
            }
        }
    }
}

// 5. ഓരോ പ്ലാനും കാണിക്കാനുള്ള കാർഡ് ഡിസൈൻ (UI Component)
@Composable
fun PlanCard(plan: Plan) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White.copy(alpha = 0.9f))
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row {
                    Text(text = plan.icon, fontSize = 20.sp, modifier = Modifier.padding(end = 8.dp))
                    Text(text = plan.title, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color.Black)
                }
                Text(text = plan.price, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF6A11CB))
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // ഫീച്ചറുകൾ ഓരോന്നായി ലിസ്റ്റ് ചെയ്യുന്നു
            plan.features.forEach { feature ->
                Text(text = "• $feature", fontSize = 14.sp, color = Color.Gray)
            }
        }
    }
}
