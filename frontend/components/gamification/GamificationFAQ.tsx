
export default function GamificationFAQ() {
    return (
        <div className="bg-surface/50 rounded-xl p-6 border border-white/10">
            <h2 className="text-2xl font-bold mb-6">❓ Frequently Asked Questions</h2>

            <div className="space-y-4">
                <div>
                    <h3 className="font-semibold mb-2 text-gray-200">Why am I "Goblin" with $0?</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">
                        That is normal! Goblin is the <strong>starting tier</strong> ($0-$100). Everyone starts here to learn safely with smaller position sizes.
                    </p>
                </div>

                <div>
                    <h3 className="font-semibold mb-2 text-gray-200">How do I level up?</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">
                        Your level updates automatically based on your <strong>Wallet Balance</strong>:
                        <br />• Reach <strong>$100 USDC</strong> to become a Mercenary.
                        <br />• Reach <strong>$500 USDC</strong> to become a Whale.
                    </p>
                </div>

                <div>
                    <h3 className="font-semibold mb-2 text-gray-200">Can I trade BTC as a Goblin?</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">
                        No, BTC/ETH are reserved for Whales (Kings Tier). Lower tiers focus on higher volatility assets (Casino/Growth) to build capital faster.
                        <br />
                        <em className="text-xs opacity-70">*Manual trading is not restricted.</em>
                    </p>
                </div>

                <div>
                    <h3 className="font-semibold mb-2 text-gray-200">What happens if I lose money?</h3>
                    <p className="text-sm text-gray-400 leading-relaxed">
                        If your balance drops below the threshold, you will be demoted to the previous level to protect your remaining capital with stricter risk limits.
                    </p>
                </div>
            </div>
        </div>
    )
}
